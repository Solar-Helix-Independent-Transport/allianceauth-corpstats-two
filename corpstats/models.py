import logging
import os
import json 
from django.core.serializers.json import DjangoJSONEncoder

from allianceauth.authentication.models import CharacterOwnership, UserProfile
from bravado.exception import HTTPForbidden
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from jsonschema.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone

from esi.errors import TokenError
from esi.models import Token
from allianceauth.eveonline.models import EveCorporationInfo, EveCharacter
from allianceauth.notifications import notify

from allianceauth.services.hooks import ServicesHook
from allianceauth.eveonline.evelinks import eveimageserver
from .managers import CorpStatManager

from .provider import esi

logger = logging.getLogger(__name__)


SERVICE_DB = {
    "mumble":"mumble",
    "smf":"smf",
    "discord":"discord",
    "discorse":"discourse",
    "Wiki JS":"wikijs",
    "ips4":"ips4",
    "openfire":"openfire",
    "phpbb3":"phpbb3",
    "teamspeak3":"teamspeak3",
}

class CorpStat(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    corp = models.OneToOneField(EveCorporationInfo, on_delete=models.CASCADE)
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = (
            ('view_corp_corpstats', 'Can view corp stats of their corporation.'),
            ('view_alliance_corpstats', 'Can view corp stats of members of their alliance.'),
            ('view_state_corpstats', 'Can view corp stats of members of their auth state.'),
            ('view_all_corpstats', 'Can view all corp stats.'),
        )
        verbose_name = "corp stats"
        verbose_name_plural = "corp stats"

    objects = CorpStatManager()

    def __str__(self):
        return "%s for %s" % (self.__class__.__name__, self.corp)

    def update(self):
        try:
            # make sure the token owner is still in this corp
            corp_id = esi.client.Character.get_characters_character_id( 
                character_id=self.token.character_id).result()['corporation_id']
            assert corp_id == int(self.corp.corporation_id)

            # get member tracking data and retrieve member ids for translation
            tracking = esi.client.Corporation.get_corporations_corporation_id_membertracking(
                corporation_id=self.corp.corporation_id,
                token=self.token.valid_access_token()).result()
            member_ids = [t['character_id'] for t in tracking]

            # requesting too many ids per call results in a HTTP400
            # the swagger spec doesn't have a maxItems count
            # manual testing says we can do over 350, but let's not risk it
            member_id_chunks = [member_ids[i:i + 255] for i in range(0, len(member_ids), 255)]
            member_name_chunks = [esi.client.Universe.post_universe_names(ids=id_chunk).result() for id_chunk in
                                  member_id_chunks]

            member_list = {t['character_id']: t for t in tracking}
            for name_chunk in member_name_chunks:
                for name in name_chunk:
                    member_list[name['id']]['character_name'] = name.get('name', "")

            # get ship and location names  
            # TODO make this fast!
            for t in tracking:
                t['ship_type_name'] = ""
                if 'ship_type_id' in t: # non req'd esi model
                    if t['ship_type_id'] is not None:
                        try:
                            t['ship_type_name'] = esi.client.Universe.get_universe_types_type_id(type_id=t['ship_type_id']).result()['name'] #TODO use the inbuilt eve provider
                        except ValidationError as e:
                            logger.error(e)
                            pass  # Bad id or crappy esi call...

                #locations = c.Universe.post_universe_names(ids=[t['location_id']]).result()
                #t['location_name'] = locations[0]['name'] if locations else ''  # might be a citadel we can't know about

                member_list[t['character_id']].update(t)

            # purge old members
            old_members = CorpMember.objects.filter(corpstats=self)
            if old_members.exists():
                old_members._raw_delete(old_members.db)

            member_db_create = []
            # bulk update and create new member models
            for c_id, data in member_list.items():
                member_db_create.append(CorpMember(corpstats=self, **data))

            CorpMember.objects.bulk_create(member_db_create)
            # update the timer
            self.save()

        except TokenError as e:
            logger.warning("%s failed to update: %s" % (self, e))
            if self.token.user:
                notify(self.token.user, "%s failed to update with your ESI token." % self,
                       message="Your token has expired or is no longer valid. Please add a new one to create a new CorpStats.",
                       level="error")
            self.delete()
        except HTTPForbidden as e:
            logger.warning("%s failed to update: %s" % (self, e))
            if self.token.user:
                notify(self.token.user, "%s failed to update with your ESI token." % self,
                       message="%s: %s" % (e.status_code, e.message), level="error")
            self.delete()
        except AssertionError as e:
            logger.warning("%s token character no longer in corp." % self)
            if self.token.user:
                notify(self.token.user, "%s cannot update with your ESI token." % self,
                       message="%s cannot update with your ESI token as you have left corp." % self, level="error")
            self.delete()

    def build_cache_key(self):
        return f"CORPSTAT_{self.corp_id}"
    
    def get_cached_overview(self):
        data = cache.get(self.build_cache_key, False)
        if data:
            return json.loads(data)
        else:
            return self.get_and_cache_stats(only_context=True)

    def get_and_cache_stats(self, only_context=False):
        members, mains, orphans, unregistered, total_mains, total_unreg, total_members, auth_percent, alt_ratio, service_percent, tracking, services = self.get_stats()
        context = {
                "corp_name":self.corp.corporation_name,
                "total_mains":total_mains,
                "total_members":total_members,
                "authd_members":len(members),
                "auth_percent":auth_percent,
                "service_percent":service_percent,
                "alt_ratio":alt_ratio,
                "orphan_count":len(orphans)
        }
        cache.set(self.build_cache_key, json.dumps({"date":timezone.now(), "data":context}, cls=DjangoJSONEncoder),43200)
        if only_context:
            return {"date":timezone.now(), "data":context}

        return members, mains, orphans, unregistered, total_mains, total_unreg, total_members, auth_percent, alt_ratio, service_percent, tracking, services

    def get_stats(self):
        """
        return all corpstats for corp

        :return:
        Mains with Alts Dict
        Members List[EveCharacter]
        Un-registered QuerySet[CorpMember]
        """

        linked_chars = EveCharacter.objects.filter(corporation_id=self.corp.corporation_id)  # get all authenticated characters in corp from auth internals
        linked_chars = linked_chars | EveCharacter.objects.filter(
            character_ownership__user__profile__main_character__corporation_id=self.corp.corporation_id)  # add all alts for characters in corp

        services = [svc.name for svc in ServicesHook.get_services()] # services list

        linked_chars = linked_chars.select_related('character_ownership',
                                                    'character_ownership__user__profile__main_character') \
            .prefetch_related('character_ownership__user__character_ownerships') \
        
        skiped_services = []
        for service in services:
            if service in SERVICE_DB:
                linked_chars = linked_chars.select_related("character_ownership__user__{}".format(SERVICE_DB[service]))
            else:
                skiped_services.append(service)
                logger.error(f"Unknown Service {service} Skipping")

        for service in skiped_services:
            services.remove(service)

        linked_chars = linked_chars.order_by('character_name')  # order by name

        members = [] # member list
        orphans = [] # orphan list
        alt_count = 0 # 
        services_count = {} # for the stats
        for service in services:
            services_count[service] = 0 # prefill

        mains = {} # main list
        temp_ids = [] # filter out linked vs unreg'd
        for char in linked_chars:
            try:
                main = char.character_ownership.user.profile.main_character # main from profile
                if main is not None: 
                    if main.corporation_id == self.corp.corporation_id: # iis this char in corp
                        if main.character_id not in mains: # add array
                            mains[main.character_id] = {
                                'main':main,
                                'alts':[], 
                                'services':{}
                                }
                            for service in services:
                                mains[main.character_id]['services'][service] = False # pre fill

                        if char.character_id == main.character_id:
                            for service in services:
                                try:
                                    if hasattr(char.character_ownership.user, SERVICE_DB[service]):
                                        mains[main.character_id]['services'][service] = True
                                        services_count[service] += 1
                                except Exception as e:
                                    logger.error(e)

                        mains[main.character_id]['alts'].append(char) #add to alt listing
                    
                    if char.corporation_id == self.corp.corporation_id:
                        members.append(char) # add to member listing as a known char
                        if not char.character_id == main.character_id:
                            alt_count += 1
                        if main.corporation_id != self.corp.corporation_id:
                            orphans.append(char)

                    temp_ids.append(char.character_id) # exclude from un-authed

            except ObjectDoesNotExist: # main not found we are unauthed
                pass

        unregistered = CorpMember.objects.filter(corpstats=self).exclude(character_id__in=temp_ids) # filter corpstat list for unknowns
        tracking = CorpMember.objects.filter(corpstats=self).filter(character_id__in=temp_ids) # filter corpstat list for unknowns


        # yay maths
        total_mains = len(mains)
        total_unreg = len(unregistered)
        total_members = len(members) + total_unreg  # is unreg + known
        # yay more math
        auth_percent = len(members)/total_members*100
        alt_ratio = 0

        try:
            alt_ratio = total_mains/alt_count
        except:
            pass
        # services
        service_percent = {}
        for service in services:
            if service in SERVICE_DB:
                try:
                    service_percent[service] = {"cnt":services_count[service], "percent":services_count[service]/total_mains*100}
                except Exception as e:
                    service_percent[service] = {"cnt":services_count[service], "percent":0}

        return members, mains, orphans, unregistered, total_mains, total_unreg, total_members, auth_percent, alt_ratio, service_percent, tracking, services

    def visible_to(self, user):
        return CorpStat.objects.filter(pk=self.pk).visible_to(user).exists()

    def can_update(self, user):
        return self.token.user == user or self.visible_to(user)

    def corp_logo(self, size=128):
        return eveimageserver.corporation_logo_url(self.corp.corporation_id, size=size)

    def alliance_logo(self, size=128):
        if self.corp.alliance_id:
            return eveimageserver.alliance_logo_url(self.corp.alliance.alliance_id, size=size)
        else:
            return eveimageserver.alliance_logo_url(1, size=size)


class CorpMember(models.Model):
    character_id = models.PositiveIntegerField()
    character_name = models.CharField(max_length=50)  # allegedly

    location_id = models.BigIntegerField(null=True, default=None)
    location_name = models.CharField(blank=True, null=True, default=None, max_length=150)  # this was counted

    ship_type_id = models.PositiveIntegerField(null=True, default=None)
    ship_type_name = models.CharField(max_length=42, null=True, default=None)  # this was also counted

    start_date = models.DateTimeField(null=True, default=None)
    logon_date = models.DateTimeField(null=True, default=None)
    logoff_date = models.DateTimeField(null=True, default=None)

    base_id = models.PositiveIntegerField(blank=True, null=True)

    corpstats = models.ForeignKey(CorpStat, on_delete=models.CASCADE, related_name='members')

    class Meta:
        # not making character_id unique in case a character moves between two corps while only one updates
        unique_together = ('corpstats', 'character_id')
        ordering = ['character_name']

    def __str__(self):
        return self.character_name

    def portrait_url(self, size=32):
        return eveimageserver.character_portrait_url(self.character_id, size=size)

    def __getattr__(self, item):
        if item.startswith('portrait_url_'):
            size = int(item.strip('portrait_url_'))
            return self.portrait_url(size)
        return self.__getattribute__(item)
