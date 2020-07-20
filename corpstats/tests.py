from unittest import mock

from django.test import TestCase
from django.utils.timezone import now
from allianceauth.tests.auth_utils import AuthUtils
from .models import CorpStat, CorpMember
from allianceauth.eveonline.models import EveCorporationInfo, EveAllianceInfo, EveCharacter
from esi.models import Token
from esi.errors import TokenError
from bravado.exception import HTTPForbidden
from django.contrib.auth.models import User, Permission
from allianceauth.authentication.models import CharacterOwnership
from django.core.cache import cache
from .provider import esi
from jsonschema.exceptions import ValidationError

class CorpStatsManagerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_id='3', alliance_name='TEST')
        cls.user.profile.refresh_from_db()
        cls.user2 = AuthUtils.create_user('test2')
        AuthUtils.add_main_character(cls.user2, 'another test character', '5', corp_id='4', corp_name='another_test_corp', corp_ticker='TEST2', alliance_id='6', alliance_name='TEST2')
        cls.user2.profile.refresh_from_db()
        cls.user3 = AuthUtils.create_user('test3')
        AuthUtils.add_main_character(cls.user2, 'yet_another test character', '9', corp_id='7', corp_name='yet_another_test_corp', corp_ticker='TEST3')

        cls.user2.profile.refresh_from_db()
        cls.alliance = EveAllianceInfo.objects.create(alliance_id=3, alliance_name='test alliance', alliance_ticker='TEST', executor_corp_id=2)
        cls.corp = EveCorporationInfo.objects.create(corporation_id=2, corporation_name='test corp', corporation_ticker='TEST', alliance=cls.alliance, member_count=1)
        cls.alliance2 = EveAllianceInfo.objects.create(alliance_id=6, alliance_name='another test alliance', alliance_ticker='TEST2', executor_corp_id=4)
        cls.corp2 = EveCorporationInfo.objects.create(corporation_id=4, corporation_name='another test corp', corporation_ticker='TEST2', alliance=cls.alliance2, member_count=1)
        cls.corp3 = EveCorporationInfo.objects.create(corporation_id=7, corporation_name='yet_another test corp', corporation_ticker='TEST3', alliance=None, member_count=1)
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id=1, character_name='test character', character_owner_hash='z')
        cls.corpstat = CorpStat.objects.create(corp=cls.corp, token=cls.token)
        cls.token2 = Token.objects.create(user=cls.user2, access_token='b', character_id=5, character_name='another test character', character_owner_hash='y')
        cls.corpstat2 = CorpStat.objects.create(corp=cls.corp2, token=cls.token2)
        cls.token3 = Token.objects.create(user=cls.user3, access_token='c', character_id=9, character_name='yet_another test character', character_owner_hash='x')
        cls.corpstat3 = CorpStat.objects.create(corp=cls.corp3, token=cls.token3)
        cls.view_all_corp_permission = Permission.objects.get_by_natural_key('view_all_corpstats', 'corpstats', 'corpstat')
        cls.view_corp_permission = Permission.objects.get_by_natural_key('view_corp_corpstats', 'corpstats', 'corpstat')
        cls.view_alliance_permission = Permission.objects.get_by_natural_key('view_alliance_corpstats', 'corpstats', 'corpstat')
        cls.view_state_permission = Permission.objects.get_by_natural_key('view_state_corpstats', 'corpstats', 'corpstat')
        cls.add_permission = Permission.objects.get_by_natural_key('view_state_corpstats', 'corpstats', 'corpstat')
        cls.state = AuthUtils.create_state('test state', 500)

        AuthUtils.assign_state(cls.user, cls.state, disconnect_signals=True)

    def setUp(self):
        self.user.refresh_from_db()
        self.user.user_permissions.clear()
        self.user2.refresh_from_db()
        self.user2.user_permissions.clear()
        self.state.refresh_from_db()
        self.state.member_corporations.clear()
        self.state.member_alliances.clear()
        self.user.is_superuser = False


    def test_visible_corporation(self):
        user = User.objects.get(pk=self.user.pk)
        user.user_permissions.add(self.view_corp_permission)
        cs = CorpStat.objects.visible_to(user)
        self.assertIn(self.corpstat, cs)
        self.assertNotIn(self.corpstat2, cs)

    def test_visible_state_corp_member(self):
        self.state.member_corporations.add(self.corp)
        user = User.objects.get(pk=self.user.pk)
        user.user_permissions.add(self.view_state_permission)
        cs = CorpStat.objects.visible_to(user)
        self.assertIn(self.corpstat, cs)
        self.assertNotIn(self.corpstat2, cs)

    def test_visible_state_alliance_member(self):
        self.state.member_alliances.add(self.alliance)
        user = User.objects.get(pk=self.user.pk)
        user.user_permissions.add(self.view_state_permission)
        cs = CorpStat.objects.visible_to(user)
        self.assertIn(self.corpstat, cs)
        self.assertNotIn(self.corpstat2, cs)

    def test_visible_alliance_member(self):
        user = User.objects.get(pk=self.user.pk)
        user.user_permissions.add(self.view_alliance_permission)
        cs = CorpStat.objects.visible_to(user)
        self.assertIn(self.corpstat, cs)
        self.assertNotIn(self.corpstat2, cs)
        self.assertNotIn(self.corpstat3, cs)

    def test_visible_superuser(self):
        user = User.objects.get(pk=self.user.pk)
        user.is_superuser = True
        cs = CorpStat.objects.visible_to(user)
        self.assertIn(self.corpstat, cs)
        self.assertIn(self.corpstat2, cs)


class CorpStatsUpdateTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        EveAllianceInfo.objects.all().delete()
        EveCorporationInfo.objects.all().delete()
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_id='3', alliance_name='TEST')
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id=1, character_name='test character', character_owner_hash='z')
        cls.corp = EveCorporationInfo.objects.create(corporation_id=2, corporation_name='test corp', corporation_ticker='TEST', member_count=1)
        cache.clear()

    def setUp(self):
        self.corpstat = CorpStat.objects.get_or_create(token=self.token, corp=self.corp)[0]
        cache.clear()
        esi._client = None

    def test_can_update(self):
        self.assertTrue(self.corpstat.can_update(self.user))
        self.corpstat.token.user = None
        self.assertFalse(self.corpstat.can_update(self.user))
        self.user.is_superuser = True
        self.assertTrue(self.corpstat.can_update(self.user))
        self.user.refresh_from_db()
        self.corpstat.token.refresh_from_db()

    @mock.patch('esi.clients.SwaggerClient')
    def test_update_add_member(self, SwaggerClient):
        SwaggerClient.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.return_value = [
            {'character_id': 1, 'ship_type_id': 2, 'location_id': 3, 'logon_date': now(), 'logoff_date': now(), 'start_date': now()}]
        SwaggerClient.return_value.Universe.get_universe_types_type_id.return_value.result.return_value = {'name': 'test ship'}
        SwaggerClient.return_value.Universe.post_universe_names.return_value.result.return_value = [{'id': 1, 'name': 'test character', 'category':'character'}]

        self.corpstat.update()
        self.assertTrue(CorpMember.objects.filter(character_id=1, character_name='test character', corpstats=self.corpstat).exists())

    @mock.patch('esi.clients.SwaggerClient')
    def test_update_add_no_extras(self, SwaggerClient):
        SwaggerClient.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.return_value = [
            {'character_id': 2, 'ship_type_id': None, 'logon_date': now(), 'logoff_date': now(), 'start_date': now()}]
        SwaggerClient.return_value.Universe.get_universe_types_type_id.return_value.result.side_effect = ValidationError("Test Failure")
        SwaggerClient.return_value.Universe.post_universe_names.return_value.result.return_value = [{'id': 2, 'name': 'test character none', 'category':'character'}]

        self.corpstat.update()
        self.assertTrue(CorpMember.objects.filter(character_id=2, character_name='test character none', corpstats=self.corpstat).exists())

    @mock.patch('esi.clients.SwaggerClient')
    def test_update_remove_member(self, SwaggerClient):
        CorpMember.objects.create(character_id='2', character_name='old test character', corpstats=self.corpstat, location_id=1, location_name='test', ship_type_id=1, ship_type_name='test', logoff_date=now(), logon_date=now(), start_date=now())
        SwaggerClient.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.return_value = [{'character_id': 1, 'ship_type_id': 2, 'location_id': 3, 'logon_date': now(), 'logoff_date': now(), 'start_date': now()}]
        SwaggerClient.return_value.Universe.get_universe_types_type_id.return_value.result.return_value = {'name': 'test ship'}
        SwaggerClient.return_value.Universe.post_universe_names.return_value.result.return_value = [{'id': 1, 'name': 'test character', 'category':'character'}]
        self.corpstat.update()
        self.assertFalse(CorpMember.objects.filter(character_id='2', corpstats=self.corpstat).exists())

    @mock.patch('corpstats.models.notify')
    @mock.patch('esi.clients.SwaggerClient')
    def test_update_deleted_token(self, SwaggerClient, notify):
        SwaggerClient.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.side_effect = TokenError()
        self.corpstat.update()
        self.assertFalse(CorpStat.objects.filter(corp=self.corp).exists())
        self.assertTrue(notify.called)

    @mock.patch('corpstats.models.notify')
    @mock.patch('esi.clients.SwaggerClient')
    def test_update_http_forbidden(self, SwaggerClient, notify):
        SwaggerClient.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.side_effect = HTTPForbidden(mock.Mock())
        self.corpstat.update()
        self.assertFalse(CorpStat.objects.filter(corp=self.corp).exists())
        self.assertTrue(notify.called)

    @mock.patch('corpstats.models.notify')
    @mock.patch('esi.clients.SwaggerClient')
    def test_update_token_character_corp_changed(self, SwaggerClient, notify):
        SwaggerClient.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 5}
        self.corpstat.update()
        self.assertFalse(CorpStat.objects.filter(corp=self.corp).exists())
        self.assertTrue(notify.called)


class CorpStatsPropertiesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_name='TEST')
        cls.user.profile.refresh_from_db()
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id='1', character_name='test character', character_owner_hash='z')
        cls.alliance = EveAllianceInfo.objects.create(alliance_id=3, alliance_name='test alliance', alliance_ticker='TEST', executor_corp_id=2)
        cls.corp = EveCorporationInfo.objects.create(corporation_id=2, corporation_name='test corp', corporation_ticker='TEST', alliance_id=cls.alliance.id, member_count=1)
        cls.corp.alliance = cls.alliance
        cls.corp.save()
        cls.corpstat = CorpStat.objects.create(token=cls.token, corp=cls.corp)
        cls.character = EveCharacter.objects.create(character_name='another test character', character_id=4, corporation_id=2, corporation_name='test corp', corporation_ticker='TEST')
        AuthUtils.disconnect_signals()
        CharacterOwnership.objects.create(character=cls.character, user=cls.user, owner_hash='a')
        AuthUtils.connect_signals()

    def test_logos(self):
        self.assertEqual(self.corpstat.corp_logo(size=128), self.corp.logo_url_128)
        self.assertEqual(self.corpstat.alliance_logo(size=128),  self.alliance.logo_url_128)


class CorpMemberTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_id='3', alliance_name='TEST')
        cls.user.profile.refresh_from_db()
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id=1, character_name='test character', character_owner_hash='a')
        cls.corp = EveCorporationInfo.objects.create(corporation_id=2, corporation_name='test corp', corporation_ticker='TEST', member_count=1)
        cls.corpstat = CorpStat.objects.create(token=cls.token, corp=cls.corp)
        cls.member = CorpMember.objects.create(corpstats=cls.corpstat, character_id=2, character_name='other test character', location_id=1, location_name='test', ship_type_id=1, ship_type_name='test', logoff_date=now(), logon_date=now(), start_date=now())

    def test_portrait_url(self):
        self.assertEquals(self.member.portrait_url(size=32), self.member.portrait_url_32)
