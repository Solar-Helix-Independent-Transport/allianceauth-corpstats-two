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

class CorpStatsManagerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_id='3', alliance_name='TEST')
        cls.user.profile.refresh_from_db()
        cls.alliance = EveAllianceInfo.objects.create(alliance_id='3', alliance_name='test alliance', alliance_ticker='TEST', executor_corp_id='2')
        cls.corp = EveCorporationInfo.objects.create(corporation_id='2', corporation_name='test corp', corporation_ticker='TEST', alliance=cls.alliance, member_count=1)
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id='1', character_name='test character', character_owner_hash='z')
        cls.corpstat = CorpStat.objects.create(corp=cls.corp, token=cls.token)
        cls.view_corp_permission = Permission.objects.get_by_natural_key('view_corp_corpstats', 'corpstats', 'corpstat')
        cls.view_alliance_permission = Permission.objects.get_by_natural_key('view_alliance_corpstats', 'corpstats', 'corpstat')
        cls.view_state_permission = Permission.objects.get_by_natural_key('view_state_corpstats', 'corpstats', 'corpstat')
        cls.state = AuthUtils.create_state('test state', 500)
        AuthUtils.assign_state(cls.user, cls.state, disconnect_signals=True)


    def setUp(self):
        self.user.refresh_from_db()
        self.user.user_permissions.clear()
        self.state.refresh_from_db()
        self.state.member_corporations.clear()
        self.state.member_alliances.clear()

    def test_visible_superuser(self):
        self.user.is_superuser = True
        cs = CorpStat.objects.visible_to(self.user)
        self.assertIn(self.corpstat, cs)

    def test_visible_corporation(self):
        self.user.user_permissions.add(self.view_corp_permission)
        cs = CorpStat.objects.visible_to(self.user)
        self.assertIn(self.corpstat, cs)

    def test_visible_alliance(self):
        self.user.user_permissions.add(self.view_alliance_permission)
        print(CorpStat.objects.all())

        cs = CorpStat.objects.visible_to(self.user)
        self.assertIn(self.corpstat, cs)

    def test_visible_state_corp_member(self):
        self.state.member_corporations.add(self.corp)
        self.user.user_permissions.add(self.view_state_permission)
        cs = CorpStat.objects.visible_to(self.user)
        self.assertIn(self.corpstat, cs)

    def test_visible_state_alliance_member(self):
        self.state.member_alliances.add(self.alliance)
        self.user.user_permissions.add(self.view_state_permission)
        cs = CorpStat.objects.visible_to(self.user)
        self.assertIn(self.corpstat, cs)


class CorpStatsUpdateTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_id='3', alliance_name='TEST')
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id='1', character_name='test character', character_owner_hash='z')
        cls.corp = EveCorporationInfo.objects.create(corporation_id='2', corporation_name='test corp', corporation_ticker='TEST', member_count=1)


    def setUp(self):
        self.corpstat = CorpStat.objects.get_or_create(token=self.token, corp=self.corp)[0]


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
        SwaggerClient.from_spec.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.from_spec.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.return_value = [
            {'character_id': 1, 'ship_type_id': 2, 'location_id': 3, 'logon_date': now(), 'logoff_date': now(), 'start_date': now()}]
        SwaggerClient.from_spec.return_value.Character.get_characters_names.return_value.result.return_value = [{'character_id': 1, 'character_name': 'test character'}]
        SwaggerClient.from_spec.return_value.Universe.get_universe_types_type_id.return_value.result.return_value = {'name': 'test ship'}
        SwaggerClient.from_spec.return_value.Universe.post_universe_names.return_value.result.return_value = [{'name': 'test system'}]

        self.corpstat.update()
        print(CorpMember.objects.all())
        self.assertTrue(CorpMember.objects.filter(character_id=1, character_name='test character', corpstats=self.corpstat).exists())

    @mock.patch('esi.clients.SwaggerClient')
    def test_update_remove_member(self, SwaggerClient):
        CorpMember.objects.create(character_id='2', character_name='old test character', corpstats=self.corpstat, location_id=1, location_name='test', ship_type_id=1, ship_type_name='test', logoff_date=now(), logon_date=now(), start_date=now())
        SwaggerClient.from_spec.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.from_spec.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.return_value = [{'character_id': 1, 'ship_type_id': 2, 'location_id': 3, 'logon_date': now(), 'logoff_date': now(), 'start_date': now()}]
        SwaggerClient.from_spec.return_value.Character.get_characters_names.return_value.result.return_value = [{'character_id': 1, 'character_name': 'test character'}]
        SwaggerClient.from_spec.return_value.Universe.get_universe_types_type_id.return_value.result.return_value = {'name': 'test ship'}
        SwaggerClient.from_spec.return_value.Universe.post_universe_names.return_value.result.return_value = [{'name': 'test system'}]
        self.corpstat.update()
        self.assertFalse(CorpMember.objects.filter(character_id='2', corpstats=self.corpstat).exists())

    @mock.patch('corpstats.models.notify')
    @mock.patch('esi.clients.SwaggerClient')
    def test_update_deleted_token(self, SwaggerClient, notify):
        SwaggerClient.from_spec.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.from_spec.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.side_effect = TokenError()
        self.corpstat.update()
        self.assertFalse(CorpStat.objects.filter(corp=self.corp).exists())
        self.assertTrue(notify.called)

    @mock.patch('corpstats.models.notify')
    @mock.patch('esi.clients.SwaggerClient')
    def test_update_http_forbidden(self, SwaggerClient, notify):
        SwaggerClient.from_spec.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 2}
        SwaggerClient.from_spec.return_value.Corporation.get_corporations_corporation_id_membertracking.return_value.result.side_effect = HTTPForbidden(mock.Mock())
        self.corpstat.update()
        self.assertFalse(CorpStat.objects.filter(corp=self.corp).exists())
        self.assertTrue(notify.called)

    @mock.patch('corpstats.models.notify')
    @mock.patch('esi.clients.SwaggerClient')
    def test_update_token_character_corp_changed(self, SwaggerClient, notify):
        SwaggerClient.from_spec.return_value.Character.get_characters_character_id.return_value.result.return_value = {'corporation_id': 3}
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
        cls.alliance = EveAllianceInfo.objects.create(alliance_id=3, alliance_name='test alliance', alliance_ticker='TEST', executor_corp_id='2')
        cls.corp = EveCorporationInfo.objects.create(corporation_id='2', corporation_name='test corp', corporation_ticker='TEST', alliance_id=3, member_count=1)
        cls.corp.alliance = cls.alliance
        cls.corp.save()
        cls.corpstat = CorpStat.objects.create(token=cls.token, corp=cls.corp)
        cls.character = EveCharacter.objects.create(character_name='another test character', character_id='4', corporation_id='2', corporation_name='test corp', corporation_ticker='TEST')
        AuthUtils.disconnect_signals()
        CharacterOwnership.objects.create(character=cls.character, user=cls.user, owner_hash='a')
        AuthUtils.connect_signals()

    def test_logos(self):
        self.assertEqual(self.corpstat.corp_logo(size=128), 'https://image.eveonline.com/Corporation/2_128.png')
        self.assertEqual(self.corpstat.alliance_logo(size=128), 'https://image.eveonline.com/Alliance/3_128.png')


class CorpMemberTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user('test')
        AuthUtils.add_main_character(cls.user, 'test character', '1', corp_id='2', corp_name='test_corp', corp_ticker='TEST', alliance_id='3', alliance_name='TEST')
        cls.user.profile.refresh_from_db()
        cls.token = Token.objects.create(user=cls.user, access_token='a', character_id='1', character_name='test character', character_owner_hash='a')
        cls.alliance = EveAllianceInfo.objects.create(alliance_id='3', alliance_name='test alliance', alliance_ticker='TEST', executor_corp_id='2')
        cls.corp = EveCorporationInfo.objects.create(corporation_id='2', corporation_name='test corp', corporation_ticker='TEST', alliance_id=3, member_count=1)
        cls.corpstat = CorpStat.objects.create(token=cls.token, corp=cls.corp)
        cls.member = CorpMember.objects.create(corpstats=cls.corpstat, character_id='2', character_name='other test character', location_id=1, location_name='test', ship_type_id=1, ship_type_name='test', logoff_date=now(), logon_date=now(), start_date=now())

    def test_portrait_url(self):
        self.assertEquals(self.member.portrait_url(size=32), 'https://image.eveonline.com/Character/2_32.jpg')
        self.assertEquals(self.member.portrait_url(size=32), self.member.portrait_url_32)
