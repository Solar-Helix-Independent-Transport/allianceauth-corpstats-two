from django.urls import re_path
from . import views

app_name = 'corpstat'

urlpatterns = [
    re_path(r'^$', views.corpstat_view, name='view'),
    re_path(r'^add/$', views.corpstats_add, name='add'),
    #url(r'^alliance/(?P<alliance_id>(\d)+)/$', views.alliance_view, name='view_alliance'),
    re_path(r'^overview/$', views.overview_view, name='view_all'),
    re_path(r'^(?P<corp_id>(\d)*)/$', views.corpstat_view, name='view_corp'),
    re_path(r'^(?P<corp_id>(\d)+)/update/$', views.corpstats_update, name='update'),
    re_path(r'^(?P<corp_id>(\d)+)/export/$', views.export_corpstats, name='export'), # has no permissions
    re_path(r'^search/$', views.corpstats_search, name='search'),
    ]
