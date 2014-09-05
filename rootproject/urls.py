from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

import flp.views

urlpatterns = patterns('',
    url(r'^$', flp.views.index, name='index'),
    url(r'^blog/(?P<blogdbid>[0-9]+)$', flp.views.blog, name='blog'),
    url(r'^my-blogs$', flp.views.my_blogs, name='my-blogs'),
    url(r'^user/(@?(?P<username>[A-Za-z0-9_]{1,15}))$', flp.views.user, name='user'),
    url(r'^fetchfeeds$', flp.views.fetchfeeds),
    (r'^twitterauth/', include('twython_django_oauth.urls')),
    url(r'^admin/', include(admin.site.urls)),

)
