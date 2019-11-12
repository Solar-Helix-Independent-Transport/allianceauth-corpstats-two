from allianceauth.services.hooks import MenuItemHook, UrlHook
from django.utils.translation import ugettext_lazy as _
from allianceauth import hooks
from . import urls


class CorpStats(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(self,
                              _('Corporation Stats'),
                              'fa fa-share-alt fa-fw',
                              'corpstat:view',
                              navactive=['corpstat:'])

    def render(self, request):
        if request.user.has_perm('corpstat.view_corp_corpstats') or request.user.has_perm(
                'corpstat.view_alliance_corpstats') or request.user.has_perm(
                'corpstat.add_corpstats') or request.user.has_perm('corpstat.view_state_corpstats'):
            return MenuItemHook.render(self, request)
        return ''


@hooks.register('menu_item_hook')
def register_menu():
    return CorpStats()


@hooks.register('url_hook')
def register_url():
    return UrlHook(urls, 'corpstat', r'^corpstat/')
