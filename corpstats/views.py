import os

from bravado.exception import HTTPError
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from esi.decorators import token_required
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from django.http import HttpResponse
import csv
import re
from itertools import chain
from allianceauth.services.hooks import ServicesHook

from .models import CorpStat, CorpMember

import logging

logger = logging.getLogger(__name__)

def access_corpstats_test(user):
    return user.has_perm('corpstats.view_corp_corpstats') \
           or user.has_perm('corpstats.view_alliance_corpstats') \
           or user.has_perm('corpstats.view_state_corpstats') \
           or user.has_perm('corpstats.view_all_corpstats')


def corpstats_visible_to_user(view):
    def check_corpstats(request, corp_id=None):
        if corp_id:
            corp = get_object_or_404(EveCorporationInfo, corporation_id=corp_id)
            corpstats = get_object_or_404(CorpStat, corp=corp)

            # get available models
            available = CorpStat.objects.visible_to(request.user)

            # ensure we can see the requested model
            if corpstats and corpstats not in available:
                raise PermissionDenied('You do not have permission to view the selected corporation statistics module.')
        else:
            corpstats = None
        return view(request, corpstats, corp_id=corp_id)
    return check_corpstats


@login_required
@user_passes_test(access_corpstats_test)
@permission_required('corpstats.add_corpstat')
@token_required(scopes=['esi-corporations.track_members.v1', 'esi-universe.read_structures.v1'])
def corpstats_add(request, token):
    try:
        if EveCharacter.objects.filter(character_id=token.character_id).exists():
            corp_id = EveCharacter.objects.get(character_id=token.character_id).corporation_id
        else:
            corp_id = \
                token.get_esi_client().Character.get_characters_character_id(
                    character_id=token.character_id).result()['corporation_id']
        try:
            corp = EveCorporationInfo.objects.get(corporation_id=corp_id)
        except EveCorporationInfo.DoesNotExist:
            corp = EveCorporationInfo.objects.create_corporation(corp_id)
        cs = CorpStat.objects.create(token=token, corp=corp)
        try:
            cs.update()
        except HTTPError as e:
            messages.error(request, str(e))
        assert cs.pk  # ensure update was successful
        if CorpStat.objects.filter(pk=cs.pk).visible_to(request.user).exists():
            return redirect('corpstat:view_corp', corp_id=corp.corporation_id)
    except IntegrityError:
        messages.error(request, _('Selected corp already has a statistics module.'))
    except AssertionError:
        messages.error(request, _('Failed to gather corporation statistics with selected token.'))
    return redirect('corpstat:view')

@login_required
@user_passes_test(access_corpstats_test)
def corpstat_view(request, corp_id=None):

    corpstats = None

    # get requested model
    if corp_id:
        corp = get_object_or_404(EveCorporationInfo, corporation_id=corp_id)
        corpstats = get_object_or_404(CorpStat, corp=corp)

    # get available models
    available = CorpStat.objects.visible_to(request.user).order_by('corp__corporation_name').select_related('corp')

    # ensure we can see the requested model
    if corpstats and corpstats not in available:
        raise PermissionDenied('You do not have permission to view the selected corporation statistics module.')

    # get default model if none requested
    if not corp_id and available.count() == 1:
        corpstats = available[0]
    elif not corp_id and available.count() > 1 and request.user.profile.main_character:
        # get their main corp if available
        try:
            corpstats = available.get(corp__corporation_id=request.user.profile.main_character.corporation_id)
        except ObjectDoesNotExist:
            corpstats = available[0]

    context = {
        'available': available # list what stats are visible to user
    }

    if corpstats:
        members, mains, orphans, unregistered, total_mains, total_unreg, total_members, auth_percent, alt_ratio, service_percent, tracking, services = corpstats.get_and_cache_stats()
        # template context array
        context.update({
            'corpstats': corpstats,
            'members': members,
            'mains': mains,
            'orphans': orphans,
            'total_orphans': len(orphans),
            'total_mains': total_mains,
            'total_members': total_members,
            'total_unreg': total_unreg,
            'auth_percent': auth_percent,
            'service_percent': service_percent,
            'alt_ratio': alt_ratio,
            'unregistered': unregistered,
            'tracking': tracking,
            "services": services
        })

    return render(request, 'corpstat/corpstats.html', context=context)  # render to template

@login_required
@user_passes_test(access_corpstats_test)
@corpstats_visible_to_user
def corpstats_update(request, corpstats, **_):
    try:
        corpstats.update()
    except HTTPError as e:
        messages.error(request, str(e))
    if corpstats.pk:
        return redirect('corpstat:view_corp', corp_id=corpstats.corp.corporation_id)
    else:
        return redirect('corpstat:view')


@login_required
@user_passes_test(access_corpstats_test)
def corpstats_search(request):
    results = []
    search_string = request.GET.get('search_string', None)
    if search_string:
        has_similar = CorpStat.objects.filter(members__character_name__icontains=search_string).visible_to(
            request.user).distinct()
        for corpstats in has_similar:
            similar = corpstats.members.filter(character_name__icontains=search_string)
            for s in similar:
                results.append((corpstats, s))
        results = sorted(results, key=lambda x: x[1].character_name)
        available = CorpStat.objects.visible_to(request.user).order_by('corp__corporation_name').select_related('corp')
        context = {
            'available': available, # list what stats are visible to user
            'results': results,
            'search_string': search_string,
        }
        return render(request, 'corpstat/search.html', context=context)
    return redirect('corpstat:view')


@login_required
@user_passes_test(access_corpstats_test)
def overview_view(request):
    # get available models
    all_corps = CorpStat.objects.visible_to(request.user)

    stats = []
    for corp in all_corps:
        stats.append(corp.get_cached_overview())

    context = {
        'available': all_corps,
        'stats': stats
    }

    return render(request, 'corpstat/alliancestats.html', context=context)


@login_required
@user_passes_test(access_corpstats_test)
@corpstats_visible_to_user
def export_corpstats(request, corpstats, **_):
    if not corpstats.members.all().exists():
        # there are no members, say there's no data
        return HttpResponse(status=204)

    many_to_many_field_names = set([many_to_many_field.name for many_to_many_field in CorpMember._meta.many_to_many])
    field_names = [field.name for field in CorpMember._meta.get_fields() if not field.auto_created
                   and field.name != 'corpstats' and field.name not in many_to_many_field_names]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % re.sub('[^\w]', '', corpstats.corp.corporation_name)

    writer = csv.writer(response)
    writer.writerow(list(chain(field_names, many_to_many_field_names)))

    for member in corpstats.members.all().order_by('character_name'):
        row = []
        for field in field_names:
            row.append('' if getattr(member, field) is None else str(getattr(member, field)))
        for field in many_to_many_field_names:
            row.extend([str(a) for a in getattr(member, field).all()])
        writer.writerow(row)

    return response
