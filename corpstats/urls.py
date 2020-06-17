from django.conf.urls import url

from . import views

app_name = 'corpstat'

urlpatterns = [
    url(r'^$', views.corpstat_view, name='view'),
    url(r'^add/$', views.corpstats_add, name='add'),
    #url(r'^alliance/(?P<alliance_id>(\d)+)/$', views.alliance_view, name='view_alliance'),
    url(r'^overview/$', views.overview_view, name='view_all'),
    url(r'^(?P<corp_id>(\d)*)/$', views.corpstat_view, name='view_corp'),
    url(r'^(?P<corp_id>(\d)+)/update/$', views.corpstats_update, name='update'),
    url(r'^(?P<corp_id>(\d)+)/export/$', views.export_corpstats, name='export'), # has no permissions
    url(r'^search/$', views.corpstats_search, name='search'),
    ]
