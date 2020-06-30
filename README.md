# CorpStats 2.0
### Electric Boogaloo!

[![Coverage Status](https://coveralls.io/repos/github/pvyParts/allianceauth-corpstats-two/badge.svg?branch=master)](https://coveralls.io/github/pvyParts/allianceauth-corpstats-two?branch=master) [![Build Status](https://travis-ci.com/pvyParts/allianceauth-corpstats-two.svg?branch=master)](https://travis-ci.com/pvyParts/allianceauth-corpstats-two)


Extended Corpstats module for [AllianceAuth](https://gitlab.com/allianceauth/allianceauth) with some extra features around corp member tracking, and auth utilization.

Includes:
 * Corp level views
 * Corp Overview views
 * Member Service activation stats
 * Member Tracking
   * Last Login and Duration
   * Last known ship

Upcoming:
  * Member Location Tracking
    * Last known location of members
 
Based on the hard work of:
 * [Ariel Rin](https://gitlab.com/soratidus999/allianceauth/tree/new-corpstats)
 * [Adarnof](https://github.com/Adarnof/allianceauth/tree/new_corpstats)

Active Devs:
 * [AaronKable](https://github.com/pvyParts)
 
## Installation
 1. Install the Repo `pip install aa-corpstats-two`
 2. Add `'corpstats',` to your `INSTALLED_APPS` in your projects `local.py`
 3. run migrations and restart auth
 3. setup your perms as documented below

## Permissions
If you are coming fromn the inbuilt module simply replace your perms from `corputils` with the matching `corpstats` perm

Perm | Admin Site | Auth Site 
 --- | --- | --- 
corpstats view_corp_corpstats | None | Can view corp stats of their corporation.
corpstats view_alliance_corpstats | None | Can view corp stats of members of their alliance.
corpstats view_state_corpstats | None | Can view corp stats of members of their auth state.
corpstats view_all_corpstats | None | Can view all corp stats.
corpstats add_corpstat | Can create model | Can add new corpstats using an SSO token.
corpstats change_corpstat |Can edit model | None.
corpstats remove_corpstat | Can delete model | None.

## Usage
Is very well documented [here](https://allianceauth.readthedocs.io/en/latest/features/apps/corpstats.html?highlight=corpstats#creating-a-corp-stats)

## Contributing
Make sure you have signed the [License Agreement](https://developers.eveonline.com/resource/license-agreement) by logging in at https://developers.eveonline.com before submitting any pull requests. All bug fixes or features must not include extra superfluous formatting changes.

## Changes
1.1.0
 * Added service activation information
 * Modified alliance view to show all corpstats visible to a user
 * updated to django-esi >= 2.0.0
 * FA 5 update

1.0.4 
 * perms fixes
 
