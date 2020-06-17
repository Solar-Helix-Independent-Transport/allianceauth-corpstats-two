from django.db import models
import logging

logger = logging.getLogger(__name__)


class CorpStatQuerySet(models.QuerySet):
    def visible_to(self, user):

        if user.has_perm('corpstats.view_all_corpstats'):  # superusers and users with this permission
            logger.debug('Returning all corpstats for %s.' % user)
            return self

        try:
            char = user.profile.main_character
            assert char
            # build all accepted queries
            queries = [models.Q(token__user=user)]

            if user.has_perm('corpstats.view_corp_corpstats'):
                queries.append(models.Q(corp__corporation_id=char.corporation_id))
            if user.has_perm('corpstats.view_alliance_corpstats'):
                queries.append(models.Q(corp__alliance_id=char.alliance_id))
            if user.has_perm('corpstats.view_state_corpstats'):
                queries.append(models.Q(corp__in=user.profile.state.member_corporations.all()))
                queries.append(models.Q(
                    corp__alliance_id__in=user.profile.state.member_alliances.all().values_list('alliance_id',
                                                                                                flat=True)))
            logger.debug('%s queries for user %s visible corpstats.' % (len(queries), user))
            # filter based on queries
            query = queries.pop()
            for q in queries:
                query |= q
            return self.filter(query)
        except AssertionError:
            logger.debug('User %s has no main character. No corpstats visible.' % user)
            return self.none()


class CorpStatManager(models.Manager):
    def get_queryset(self):
        return CorpStatQuerySet(self.model, using=self._db)

    def visible_to(self, user):
        return self.get_queryset().visible_to(user)
