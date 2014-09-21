from django.core.management.base import BaseCommand, CommandError
from flp.models import Post, Score, User2Score, TwitterPostCount
import requests
from django.contrib.auth.models import User
from flp.common import publicLog, andlist
import datetime, pytz

SCORE_WHEN_IT_GETS_TWEETS = 3
MAX_AGE_OF_SCORING_POST_DAYS = 60

class Command(BaseCommand):
    args = '[url to atom file (optional)]'
    help = 'Fetches and updates the feed list'

    def handle(self, *args, **options):
        output = []
        dt = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=MAX_AGE_OF_SCORING_POST_DAYS)
        posts = Post.objects.filter(date__gte=dt)
        for post in posts:
            new_score = None
            try:
                r = requests.get("https://cdn.api.twitter.com/1/urls/count.json",
                    params={"url": post.link})
                twitter, created = TwitterPostCount.objects.get_or_create(post=post)
                new_score = r.json().get("count")
            except:
                continue
            message = None
            if new_score is not None:
                if new_score != twitter.tweet_count_at_last_check:
                    if twitter.tweet_count_at_last_check < SCORE_WHEN_IT_GETS_TWEETS and new_score >= SCORE_WHEN_IT_GETS_TWEETS:
                        users = post.blog.user2blog_set.all()
                        now = datetime.datetime.now()
                        s = Score(post=post, value=2, reason="Tweeted more than %s times" % SCORE_WHEN_IT_GETS_TWEETS, 
                            created_date=now, attached_url=post.link, 
                            month=now.month, year=now.year)
                        s.save()
                        if users.count() > 0:
                            for u in users:
                                User2Score(user=u.user, score=s).save()
                            twusernames = ["@%s" % x.user.username for x in users]
                            s = ""
                            if len(twusernames) == 1: s = "s"
                            mlen = 141
                            attempts = 0
                            uncount = len(twusernames)
                            while mlen > 140 and attempts < 10:
                                usernames = andlist(twusernames[:uncount])
                                messagetest = "A post from %s gets over %s tweets! So %s score%s some points! http://flpb.herokuapp.com" % (
                                    post.blog.name, SCORE_WHEN_IT_GETS_TWEETS, usernames, s)
                                mlen = len(messagetest)
                                if mlen <= 140: message = messagetest
                                uncount -= 1
                                attempts += 1
                    twitter.tweet_count_at_last_check = new_score
                    twitter.save()
            if message:
                #print message
                publicLog(message)
                output.append(message)
        self.stdout.write("%s scores in %s posts" % (len(output), len(posts)))


