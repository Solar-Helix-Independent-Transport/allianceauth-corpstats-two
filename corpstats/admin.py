from django.contrib import admin

from .models import CorpStat, CorpMember

admin.site.register(CorpStat)
admin.site.register(CorpMember)