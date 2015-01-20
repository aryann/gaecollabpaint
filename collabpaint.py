import constants
import os
import jinja2
import json
import webapp2

from google.appengine.api import channel
from google.appengine.api import users
from google.appengine.ext import ndb

# TODO(aryann): Allow more than one room.
DEFAULT_ROOM = 'default-room'

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Room(ndb.Model):
    users = ndb.UserProperty(repeated=True)


class LineSegments(ndb.Model):
    room = ndb.KeyProperty(kind=Room)
    xs = ndb.IntegerProperty(repeated=True)
    ys = ndb.IntegerProperty(repeated=True)
    user = ndb.UserProperty()


class Canvas(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        # TODO(aryann): Check the query param "room_key" and use it here.
        r = Room.get_or_insert(DEFAULT_ROOM)
        if user not in r.users:
            r.users.append(user)
            r.put()

        token = channel.create_channel(r.key.string_id() + user.user_id())
        template_values = {
            'room_key': r.key.string_id(),
            'width': constants.WIDTH,
            'height': constants.HEIGHT,
            'token': token,
        }
        template = JINJA_ENVIRONMENT.get_template('canvas.html')
        self.response.write(template.render(template_values))


class CanvasUpdater(webapp2.RequestHandler):

    def post(self):
        room_key = self.request.get('room_key')
        user = users.get_current_user()
        xs, ys = zip(*json.loads(self.request.body))

        line_segments = LineSegments(
            room=ndb.Key(Room, room_key),
            xs=xs,
            ys=ys,
            user=user)
        line_segments.put()

        # TODO(aryann): Broadcast the changes to all users in the
        # room.


application = webapp2.WSGIApplication([
        ('/', Canvas),
        ('/update', CanvasUpdater),
], debug=True)
