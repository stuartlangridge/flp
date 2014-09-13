from django.test import TestCase
from django.core.management import call_command
from StringIO import StringIO
from xml.dom import minidom
from flp.models import User2Blog, Blog
from django.contrib.auth.models import User
import datetime, pytz

BASE_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:planet="http://planet.intertwingly.net/" 
    xmlns:indexing="urn:atom-extension:indexing" indexing:index="no"><access:restriction 
    xmlns:access="http://www.bloglines.com/about/specs/fac-1.0" relationship="deny"/>
<title>Planet Birmingham</title>
<updated>2014-09-02T23:06:58Z</updated>
<generator uri="http://intertwingly.net/code/venus/">Venus</generator>
<author>
    <name>Birmingham.IO</name>
</author>
<id>http://planet.birmingham.io/atom.xml</id>
<link href="http://planet.birmingham.io/atom.xml" rel="self" 
type="application/atom+xml"/>
<link href="http://planet.birmingham.io/" rel="alternate"/>
%s
</feed>"""

class TwitterTestCase(TestCase):
    def make_and_append_xml(self, dic, document, parent):
        for prop in dic:
            if type(dic[prop]) == type({}):
                el = document.createElement(prop)
                self.make_and_append_xml(dic[prop], document, el)
            else:
                el = document.createElement(prop)
                el.appendChild(document.createTextNode(dic[prop]))
            parent.appendChild(el)

    def make_entries_as_atom(self, entries):
        es = []
        for entry in entries:
            e = minidom.parseString("<entry/>")
            self.make_and_append_xml(entry, e, e.firstChild)
            xml = e.toprettyxml()
            xml = xml.replace('<?xml version="1.0" ?>\n', "")
            es.append(xml)
        return "\n".join(es)

    def get_twitter_from_new_entries(self, entries):
        content = StringIO()
        atom = StringIO()
        atom.write(BASE_ATOM % self.make_entries_as_atom(entries))
        atom.seek(0)
        atom.seek(0)
        call_command('fetchfeeds', atom, stdout=content)
        content.seek(0)
        out = content.read()
        _, twitter = out.split("====== BEGIN TWITTER ======")
        twitter = "".join(twitter.split("\n")).strip()
        return twitter

    def test_calling_command_works_with_fp(self):
        """We can call the fetchfeeds command with a StringIO and get output"""
        twitter = self.get_twitter_from_new_entries([])
        self.assertEqual(twitter, "")

    def test_new_post_no_subscribers(self):
        """A new post which nobody follows"""
        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            "And Blog 1 adds a post! Wish someone had it in their team.")

    def test_new_posts_same_blog_no_subscribers(self):
        """Multiple new posts from same blog which nobody follows"""
        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        },{
            "id": "http://example.com/fred/2",
            "link": "http://example.com/fred/2",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            "And Blog 1 adds a post! Wish someone had it in their team.")

    def test_new_posts_no_subscribers(self):
        """Multiple new posts from many blogs which nobody follows"""
        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        },{
            "id": "http://example.com/barney/1",
            "link": "http://example.com/barney/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/barney",
                "title": "Blog 2"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            "Blog 1 and Blog 2 add a post! If only someone had them in their team.")

    def test_3_new_posts_no_subscribers(self):
        """Multiple new posts from many blogs which nobody follows"""
        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        },{
            "id": "http://example.com/barney/1",
            "link": "http://example.com/barney/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/barney",
                "title": "Blog 2"
            },
            "updated": "2014-09-02T18:45:59Z"
        },{
            "id": "http://example.com/wilma/1",
            "link": "http://example.com/wilma/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/wilma",
                "title": "Blog 3"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            "Blog 1, Blog 2, and Blog 3 add a post! If only someone had them in their team.")

    def test_new_post_one_subscriber(self):
        """A new post which one person follows"""

        u = User(username="u1")
        u.save()
        b = Blog(url="http://example.com/fred", name="Blog 1", price=1000)
        b.save()
        User2Blog(user=u, blog=b, price=1000, created_at=datetime.datetime.now(pytz.utc)).save()

        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            "Blog 1 adds a post! @u1 scores some points!")

    def test_new_post_many_subscribers(self):
        """A new post which many follow"""

        b = Blog(url="http://example.com/fred", name="Blog 1", price=1000)
        b.save()
        for i in range(1,10):
            u = User(username="u%s" % i)
            u.save()
            User2Blog(user=u, blog=b, price=1000, created_at=datetime.datetime.now(pytz.utc)).save()

        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            "Blog 1 adds a post! @u1, @u2, @u3, @u4, @u5, @u6, @u7, @u8, and @u9 score some points!")

    def test_new_post_long_subscribers(self):
        """A new post followed by people with long names"""

        b = Blog(url="http://example.com/fred", name="Blog 1", price=1000)
        b.save()
        for i in range(1,10):
            u = User(username=("user_name_long_is_%s" % i))
            u.save()
            User2Blog(user=u, blog=b, price=1000, created_at=datetime.datetime.now(pytz.utc)).save()

        twitter = self.get_twitter_from_new_entries([{
            "id": "http://example.com/fred/1",
            "link": "http://example.com/fred/1",
            "content": "woooo",
            "source": {
                "id": "http://example.com/fred",
                "title": "Blog 1"
            },
            "updated": "2014-09-02T18:45:59Z"
        }])
        self.assertEqual(twitter, 
            ("Blog 1 adds a post! @user_name_long_is_1, @user_name_long_is_2, @user_name_long_is_3, "
                "and @user_name_long_is_4 score some points!"))

    def test_many_new_posts_many_subscribers(self):
        """Many new posts for many people"""

        entries = []
        for i in range(1,10):
            b = Blog(url="http://example.com/b%s" % i, name="Blog %s" % i, price=1000)
            b.save()
            u = User(username="u%s" % i)
            u.save()
            User2Blog(user=u, blog=b, price=1000, 
                created_at=datetime.datetime.now(pytz.utc)).save()
            entries.append({
                "id": "http://example.com/b%s" % i + "/1",
                "link": "http://example.com/b%s" % i + "/1",
                "content": "woooo",
                "source": {
                    "id": "http://example.com/b%s" % i + "",
                    "title": "Blog %s" % i
                },
                "updated": "2014-09-02T18:45:59Z"
            })

        twitter = self.get_twitter_from_new_entries(entries)
        self.assertEqual(twitter, 
            ("Blog 1, Blog 2, Blog 3, Blog 4, Blog 5, Blog 6, Blog 7, and Blog 8 add a post! "
                "@u1, @u2, @u3, @u4, @u5, @u6, @u7, and @u8 score some points!"))

    def test_many_new_posts_many_long_subscribers(self):
        """Many new posts for many people"""

        entries = []
        for i in range(1,10):
            b = Blog(url="http://example.com/b%s" % i, name="Blog %s" % i, price=1000)
            b.save()
            u = User(username="username_is_long_%s" % i)
            u.save()
            User2Blog(user=u, blog=b, price=1000, 
                created_at=datetime.datetime.now(pytz.utc)).save()
            entries.append({
                "id": "http://example.com/b%s" % i + "/1",
                "link": "http://example.com/b%s" % i + "/1",
                "content": "woooo",
                "source": {
                    "id": "http://example.com/b%s" % i + "",
                    "title": "Blog %s" % i
                },
                "updated": "2014-09-02T18:45:59Z"
            })

        twitter = self.get_twitter_from_new_entries(entries)
        self.assertEqual(twitter, 
            ("Blog 1, Blog 2, and Blog 3 add a post! "
                "@username_is_long_1, @username_is_long_2, and "
                "@username_is_long_3 score some points!"))

    def test_many_new_long_posts_many_long_subscribers(self):
        """Many new posts for many people"""

        entries = []
        for i in range(1,10):
            b = Blog(url="http://example.com/b%s" % i, 
                name="This is a long blog name to test coping with it %s" % i, price=1000)
            b.save()
            u = User(username="username_is_long_%s" % i)
            u.save()
            User2Blog(user=u, blog=b, price=1000, 
                created_at=datetime.datetime.now(pytz.utc)).save()
            entries.append({
                "id": "http://example.com/b%s" % i + "/1",
                "link": "http://example.com/b%s" % i + "/1",
                "content": "woooo",
                "source": {
                    "id": "http://example.com/b%s" % i + "",
                    "title": "This is a long blog name to test coping with it %s" % i
                },
                "updated": "2014-09-02T18:45:59Z"
            })

        twitter = self.get_twitter_from_new_entries(entries)
        self.assertEqual(twitter, 
            "This is a long blog name to test coping with it 1 adds a post! @username_is_long_1 scores some points!")

