from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from flp.models import Blog, Post, Score, User2Blog, User2Score
import os, codecs, html5lib, re, sys, datetime, time, urlparse
import requests, feedparser
from django.db.models import Sum
from django.contrib.auth.models import User
from twython import Twython
from flp.common import publicLog, andlist

_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')
def _slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    
    From Django's "django/template/defaultfilters.py".
    """
    import unicodedata
    if not isinstance(value, unicode):
        value = unicode(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(_slugify_strip_re.sub('', value).strip().lower())
    return _slugify_hyphenate_re.sub('-', value)

class Command(BaseCommand):
    args = '[url to atom file (optional)]'
    help = 'Fetches and updates the feed list'

    def handle(self, *args, **options):
        if len(args) > 0:
            url = args[0]
            try: # explicitly specified thing to fetch
                if getattr(url, "read", None):
                    # thing specified is a file-like object. The test suite does this
                    atom = url.read()
                elif args[0].startswith("http://") or args[0].startswith("https://"):
                    atom = requests.get(url).content
                else:
                    fp = codecs.open(url)
                    atom = fp.read()
                    fp.close()
            except IOError as e:
                if e.errno == 2:
                    raise Exception("No such file %s" % args[0])
                else:
                    raise
        else:
            try:
                url = settings.PLANET_ATOM_URL
            except AttributeError:
                raise Exception(("You didn't specify a URL to fetch and there isn't "
                    "one in settings.PLANET_ATOM_URL"))
            atom = requests.get(url).content

        feed = feedparser.parse(atom)
        if "bozo_exception" in feed:
            raise Exception(
                "Could not parse Atom feed '%s', with error '%s'." % (url, feed.bozo_exception))

        blogs = dict([(entry["source"]["id"], entry["source"].get("title", entry["source"]["id"])) for entry in feed.entries])
        posts = []
        for entry in feed.entries:
            d = {
                "blog_id": entry.source.id,
                "blog_name": entry.source.get("title", entry.source.id),
                "id": entry.id,
                "date": datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed), 
                    timezone.get_default_timezone()),
                "link": entry.link,
                "author": entry.get("author")
            }
            content = ""
            if "content" in entry:
                for c in entry.content:
                    if len(c.value) > len(content):
                        content = c.value
            elif "summary_detail" in entry:
                content = entry.summary_detail.get("value", "")
            else:
                content = entry.get("summary", "")

            d["length"] = len(content)
            d["content"] = content

            posts.append(d)

        # the posts should be in date order, but for paranoia's sake...
        posts.sort(cmp=lambda a,b: cmp(a["date"], b["date"]))

        # find links in any post to any other post we know about
        posts_linking_to_one_another = {}
        # first, get a list of all post links. This is all the ones in the DB, plus all the new ones
        post_links = dict([(p["link"], p["blog_id"]) for p in posts])
        for dbpost in Post.objects.all():
            post_links[dbpost.link] = dbpost.blog.url
        # next, get all URLs in all new post content, and update the links count for any which match
        GRUBER_URLINTEXT_PAT = re.compile(ur'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')
        for post in posts:
            for foundurl in [ mgroups[0] for mgroups in GRUBER_URLINTEXT_PAT.findall(post["content"]) ]:
                if foundurl in post_links:
                    if post_links[foundurl] == post["blog_id"]:
                        # no credit for linking to your own blog!
                        continue
                    # add a link credit to the linking post
                    if post["link"] not in posts_linking_to_one_another:
                        posts_linking_to_one_another[post["link"]] = []
                    posts_linking_to_one_another[post["link"]].append({"links_to": foundurl})
                    # and to the linked-to post
                    if foundurl not in posts_linking_to_one_another:
                        posts_linking_to_one_another[foundurl] = []
                    posts_linking_to_one_another[foundurl].append({"linked_from": post["link"]})

        # Finished with post content, so remove it
        for post in posts:
            del(post["content"])
        blogs_with_updates = {}
        newly_created_blog_names = []

        # First, add any new blogs
        blogs = dict([(x["blog_id"], x["blog_name"]) for x in posts])
        twitter = {}

        for blog_id, blog_name in blogs.items():
            try:
                existing = Blog.objects.get(url=blog_id)
            except Blog.DoesNotExist:
                blog = Blog(url=blog_id, name=blog_name, price=0)
                blog.save()
                self.stdout.write(u"Added new blog '%s' (%s)" % (blog_name, blog_id))
                blogs_with_updates[blog.id] = blog
                newly_created_blog_names.append(blog_name)

        # Now, add new posts
        posts_in_db = []
        for post in posts:
            try:
                existing = Post.objects.get(post_id=post["id"])
                posts_in_db.append(post["link"])
            except Post.DoesNotExist:
                existing_blog = Blog.objects.get(url=post["blog_id"])
                newpost = Post(post_id=post["id"], blog=existing_blog, 
                    length=post["length"], date=post["date"], 
                    link=post["link"], author=post["author"])
                newpost.save()
                self.stdout.write(u"Added new post '%s'" % (post["id"],))
                blogs_with_updates[existing_blog.id] = existing_blog
                twitter[post["blog_id"]] = {"blog_name": existing_blog.name, "users": {}}


                # Now calculate any scores for that post and insert them too
                new_post_score = 6
                new_post_reason = "New post"

                previous_in_blog = Post.objects.filter(blog=existing_blog).order_by("-date")
                if previous_in_blog.count() > 1:
                    # item 0 is the one we've just inserted
                    # Reduced score for a second post in 24 hours
                    if abs((post["date"] - previous_in_blog[1].date).days) < 1:
                        new_post_score = 2
                        new_post_reason = "Second new post in 24 hours"
                        if previous_in_blog.count() > 2:
                            if (post["date"] - previous_in_blog[2].date).days < 1:
                                # zero score for a third post in 24 hours
                                new_post_score = 0

                if new_post_score > 0:
                    s = Score(post=newpost, value=new_post_score, reason=new_post_reason, 
                        created_date=post["date"], attached_url=post["link"],
                        month=post["date"].month, year=post["date"].year)
                    s.save()
                    self.stdout.write(u"Added score: %s" % s)

                    # and credit all users who own this blog with that score
                    for ub in User2Blog.objects.filter(blog=existing_blog):
                        User2Score(user=ub.user, score=s).save()
                        if ub.user.username not in twitter[post["blog_id"]]["users"]:
                            twitter[post["blog_id"]]["users"][ub.user.username] = 0
                        twitter[post["blog_id"]]["users"][ub.user.username] += new_post_score

        # Credit scores for links between posts
        for postlink, scoreitems in posts_linking_to_one_another.items():
            post = Post.objects.get(link=postlink)
            for scoreitem in scoreitems:
                if "links_to" in scoreitem:
                    if postlink in posts_in_db:
                        # this post was already in the database, and it was also in the parsed atom feed
                        # ignore that it links elsewhere, because we've already given it a score for that
                        continue
                    s = Score(post=post, value=1, reason="Links to another post", created_date=post.date,
                        attached_url=scoreitem["links_to"], month=post.date.month, year=post.date.year)
                    s.save()
                    blogs_with_updates[post.blog.id] = post.blog
                    # and credit all users who own this blog with that score
                    for user in User2Blog.objects.filter(blog=post.blog):
                        User2Score(user=user, score=s).save()
                        if user.username not in twitter[post["blog_id"]]["users"]:
                            twitter[post["blog_id"]]["users"][user.username] = 0
                        twitter[post["blog_id"]]["users"][user.username] += 1

                elif "linked_from" in scoreitem:
                    if scoreitem["linked_from"] in posts_in_db:
                        # the post linking to us was already in the database, and it was also in the parsed atom feed
                        # ignore that it linked to us, because we've already given us a score for that
                        continue
                    s= Score(post=post, value=1, reason="Linked to by another post", created_date=post.date,
                        attached_url=scoreitem["linked_from"], month=post.date.month, year=post.date.year)
                    s.save()
                    blogs_with_updates[post.blog.id] = post.blog
                    # and credit all users who own this blog with that score
                    for user in User2Blog.objects.filter(blog=post.blog):
                        User2Score(user=user, score=s).save()
                        if user.username not in twitter[post["blog_id"]]["users"]:
                            twitter[post["blog_id"]]["users"][user.username] = 0
                        twitter[post["blog_id"]]["users"][user.username] += 1

        # Calculate the price of an ideal blog, to use when calculating blog prices below
        ideal = (30 / 2) * (6 + 2)
        money = 10000.0
        ideal_blog_factor = 1.8
        #print "Theoretical ideal blog, with a post every two days which gets two links", ideal
        #print ("Assume that you can't *quite* buy an ideal blog. You get 100 nominal points, "
        #    "and with that you have to buy 5 blogs; that's one high-flyer, two mediums, and two lows.")
        #print "Those points therefore are 50 + 20 + 20 + 5 + 5."
        #print "Money you are allocated:", money
        #print "An ideal blog is worth", ideal_blog_factor * money

        # Update scores for each blog
        self.stdout.write(u"Updating scores for %s updated blogs" % len(blogs_with_updates.values()))
        now = datetime.datetime.now()
        for blog in blogs_with_updates.values():
            self.stdout.write(u"updating price for blog %s" % blog)

            average_per_month_scores = Score.objects.filter(post__blog=blog).values(
                "month", "year").annotate(total=Sum("value"))
            average_per_month_scores = sorted(average_per_month_scores,
                cmp=lambda a,b: cmp((a['year'],a['month']),(b['year'],b['month'])))

            avg_score_scoring_months = float(sum(
                [x["total"] for x in average_per_month_scores])
            ) / len(average_per_month_scores)

            # now find out how many months there have been since the first post
            thism = average_per_month_scores[0]["month"]
            thisy = average_per_month_scores[0]["year"]
            nowm = datetime.datetime.now().month
            nowy = datetime.datetime.now().year
            age = 1
            while 1:
                if thism == nowm and thisy == nowy:
                    break
                thism += 1
                if thism > 12:
                    thism = 1
                    thisy += 1
                age += 1
                if age > 1000:
                    break # paranoia
            avg_score_all_months = float(sum(
                [x["total"] for x in average_per_month_scores])) / age

            # and update current price for all updated blogs
            blog_score = (avg_score_scoring_months + 
                avg_score_all_months / 2.0) # midway between score and no-zero score
            blog_proportion = blog_score / ideal
            blog_cost = int(ideal_blog_factor * money * blog_proportion)
            blog.price = blog_cost
            blog.save()

        for name in newly_created_blog_names:
            publicLog("A new blog arrives! You may now purchase %s" % (name,))

        # Create twitter output
        self.stdout.write("\n\n====== BEGIN TWITTER ======\n")
        twitter_output = []
        scoring_users = []
        if len(twitter) == 0:
            # no new things, so no tweet
            twitter_output = []
        elif len(twitter) == 1:
            # one blog updated
            updated_blog = twitter.values()[0]
            if len(updated_blog["users"]) == 0:
                twitter_output = [
                    u"And %s adds a post!" % (updated_blog["blog_name"],),
                    u"Wish someone had it in their team."
                ]
            else:
                scoring_users += updated_blog["users"]
                score = "score"
                if len(scoring_users) == 1: score = "scores"
                twitter_output = [
                    u"%s adds a post!" % (updated_blog["blog_name"],),
                    sorted(["@%s" % x for x in scoring_users]),
                    score + u" some points!"
                ]
        else:
            # more than one blog updated
            for updated_blog in twitter.values():
                scoring_users += updated_blog["users"]
            if len(scoring_users) == 0:
                twitter_output = [
                    sorted([x["blog_name"] for x in twitter.values()]),
                    u"addSSS a post!",
                    u"If only someone had them in their team."
                ]
            else:
                twitter_output = [
                    sorted([x["blog_name"] for x in twitter.values()]),
                    u"addSSS a post!",
                    sorted(["@%s" % x for x in scoring_users]),
                    u"scoreSSS some points!"
                ]
        final_output = " " * 141
        attempts = 0
        list_decrements = {}
        while len(final_output) > 140 and attempts < 10:
            attempts += 1
            #print "Too long, attempt", attempts
            fo = []
            last_list_count = 1
            for i in range(len(twitter_output)):
                item = twitter_output[i]
                #print "got item, %r" % (item,)
                if type(item) == type([]):
                    #print "and it is a list"
                    dec_amt = list_decrements.get(i)
                    if dec_amt is None:
                        # first time through the loop
                        list_decrements[i] = len(item)
                        fo.append(andlist(item))
                        last_list_count = len(item)
                        #print "first time, appending", andlist(item)
                    elif dec_amt == 0:
                        # decreased all the way to zero, so just the first
                        fo.append(andlist([item[0]]))
                        last_list_count = 1
                        #print "deced to zero, appending", fo[-1]
                    else:
                        list_decrements[i] = list_decrements[i] - 1
                        fo.append(andlist(item[:list_decrements[i]]))
                        last_list_count = list_decrements[i]
                        #print "deced to", list_decrements[i], "appending", fo[-1]
                else:
                    if last_list_count == 1:
                        SSS = "s"
                    else:
                        SSS = ""
                    fo.append(item.replace("SSS", SSS))
            final_output = " ".join(fo)
        if final_output:
            publicLog(final_output)
        self.stdout.write(final_output)


