# FLP

This is Fantasy League Planet (whatever). The initial version points at Planet Birmingham. Basically, you get some virtual pounds to buy a selection of five blogs from the Planet aggregator of your choice, and then whenever your blogs post or get linked to you get points.

It's a Django app. Download, `pip install -r requirements.txt`, set the appropriate environment variables, `python manage.py syncdb`, then `python manage.py runserver`.

You'll need to define the following environment variables:

 * `DATABASE_URL` - a [dj-database-url](https://github.com/kennethreitz/dj-database-url) URL pointing at your database
 * `SOCIAL_AUTH_TWITTER_KEY` and `SOCIAL_AUTH_TWITTER_SECRET` - create an application on Twitter, and these are the keys it gives you
 * `SECRET_KEY` - Django uses this. Define it as some long random string.

To actually fetch the feeds, run `python manage.py fetchfeeds`. This will fetch the Atom URL `settings.PLANET_ATOM_URL` and update itself with all the blogs and posts therein. You'll probably want to run this out of cron or similar.
