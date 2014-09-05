from django.db import models
from django.contrib.auth.models import User

class Blog(models.Model):
    url = models.URLField()
    name = models.CharField(max_length=255)
    price = models.IntegerField()
    def __unicode__(self): return u'Blog (%s)' % self.name

class Post(models.Model):
    blog = models.ForeignKey(Blog)
    date = models.DateTimeField()
    length = models.IntegerField()
    post_id = models.CharField(max_length=1000)
    link = models.URLField(max_length=1000)
    author = models.CharField(max_length=255, null=True)
    def __unicode__(self): return u'Post %s' % (self.link,)

class Score(models.Model):
    post = models.ForeignKey(Post)
    value = models.IntegerField()
    reason = models.CharField(max_length=255)
    created_date = models.DateTimeField(auto_now_add=True)
    month = models.IntegerField() # stored so we can group on it because
    year = models.IntegerField()  # group by datepart() won't work across DBs
    attached_url = models.URLField(max_length=1000)
    def __unicode__(self): return u'Score %s ("%s") on %s' % (self.value, self.reason, self.post)

class User2Score(models.Model):
    user = models.ForeignKey(User)
    score = models.ForeignKey(Score)
    def __unicode__(self): return u'%s scored %s' % (self.user, self.score)

class User2Blog(models.Model):
    user = models.ForeignKey(User)
    blog = models.ForeignKey(Blog)
    price = models.IntegerField()
    created_at = models.DateTimeField()
    def __unicode__(self): return u'User %s owning %s' % (self.user, self.blog)

