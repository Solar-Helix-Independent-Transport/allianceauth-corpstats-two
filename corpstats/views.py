import os

from bravado.exception import HTTPError
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.exceptions import PermissionDenied
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

from .models import CorpStat, CorpMember


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
@corpstats_visible_to_user
def corpstat_view(request, corpstats, corp_id=None,):
    # get available models
    available = CorpStat.objects.visible_to(request.user).order_by('corp__corporation_name')

    # get default model if none requested
    if not corp_id and available.count() == 1:
        corpstats = available[0]
    elif not corp_id and available.count() > 1 and request.user.profile.main_character:
        # get their main corp if available
        try:
            corpstats = available.get(corp__corporation_id=request.user.profile.main_character.corporation_id)
        except CorpStats.DoesNotExist:
            pass

    context = {
        'available_corps': available,
        'available_alliances': CorpStat.objects.alliances_visible_to(request.user),
    }
    if corpstats:
        mains, members, unregistered, tracking = corpstats.get_stats()
        context.update({
            'mains': mains,
            'members': members,
            'unregistered_members': unregistered,
            'tracking': tracking,
            'corpstats': corpstats,
        })

    return render(request, 'corpstat/corpstats.html', context=context)


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
        context = {
            'available_corps': CorpStat.objects.visible_to(request.user),
            'available_alliances': CorpStat.objects.alliances_visible_to(request.user),
            'results': results,
            'search_string': search_string,
        }
        return render(request, 'corpstat/search.html', context=context)
    return redirect('corpstat:view')


@login_required
@user_passes_test(access_corpstats_test)
def alliance_view(request, alliance_id=None):
    # get available models
    alliances = CorpStat.objects.alliances_visible_to(request.user)

    # get default model if none requested
    if not alliance_id:
        alliance_id = request.user.profile.main_character.alliance.alliance_id
    """
    # ensure we can see the requested model
    if alliance_id not in alliances:
        raise PermissionDenied('You do not have permission to view the selected alliance statistics module.')
    """
    corpstats_temp = CorpMember.objects.values('corpstats__corp__corporation_name').annotate(total_members=Count('character_id')).order_by('corpstats__corp__corporation_name') 
    corp_totals={}
    for stat in corpstats_temp:
        corp_totals[stat['corpstats__corp__corporation_name']]=stat['total_members']
    # it's a lot easier to count member objects directly than try to walk reverse relations
    alliance_members = EveCharacter.objects.filter(character_ownership__user__profile__main_character__alliance_id=alliance_id).filter(alliance_id=alliance_id)
    corp_breakdown = {}
    
    for member in alliance_members:
        if member.corporation_name not in corp_breakdown:
            corp_breakdown[member.corporation_name] = {}
            corp_breakdown[member.corporation_name]['mains'] = 0
            corp_breakdown[member.corporation_name]['alts'] = 0
            corp_breakdown[member.corporation_name]['members'] = 0
            try: 
                corp_breakdown[member.corporation_name]['total'] = corp_totals[member.corporation_name]
            except:
                pass

        if member.character_ownership.user.profile.main_character == member:
            corp_breakdown[member.corporation_name]['mains'] += 1
        else:
            corp_breakdown[member.corporation_name]['alts'] += 1 
        corp_breakdown[member.corporation_name]['members'] += 1


    context = {
        'available_corps': CorpStat.objects.visible_to(request.user),
        'available_alliances': alliances,
        'alliance_id': alliance_id,
        'alliance_name': alliances[alliance_id],
        'corp_breakdown': corp_breakdown
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
