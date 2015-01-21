import constants
import random
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


def GenerateClientId(room_name):
    return room_name + str(random.randrange(- 2 ** 63, 2 ** 63 - 1))


class Room(ndb.Model):
    client_ids = ndb.StringProperty(repeated=True)


class LineSegments(ndb.Model):
    date_time = ndb.DateTimeProperty(auto_now_add=True)
    xs = ndb.IntegerProperty(repeated=True)
    ys = ndb.IntegerProperty(repeated=True)
    user = ndb.UserProperty()

    def GetPoints(self):
        return zip(self.xs, self.ys)

    @classmethod
    def GetLineSegmentsForRoom(cls, room_key):
        return LineSegments.query(
            ancestor=ndb.Key(Room, room_key)).order(LineSegments.date_time)


class Canvas(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        # TODO(aryann): Check the query param "room_key" and use it here.
        room = Room.get_or_insert(DEFAULT_ROOM)
        client_id = GenerateClientId(DEFAULT_ROOM)
        room.client_ids.append(client_id)
        room.put()

        token = channel.create_channel(client_id)
        template_values = {
            'room_key': room.key.string_id(),
            'width': constants.WIDTH,
            'height': constants.HEIGHT,
            'token': token,
        }
        template = JINJA_ENVIRONMENT.get_template('canvas.html')
        self.response.write(template.render(template_values))


class LinesHandler(webapp2.RequestHandler):

    def get(self):
        room_key = self.request.get('room_key')
        print room_key
        client_id = self.request.get('client_id')

        lines = []
        for line_segment in LineSegments.GetLineSegmentsForRoom(
            room_key).fetch():
            lines.append(line_segment.GetPoints())
        channel.send_message(client_id, json.dumps(lines))

    def post(self):
        room_key = self.request.get('room_key')
        user = users.get_current_user()

        line_segments = json.loads(self.request.body)
        if not line_segments:
            return

        xs, ys = zip(*line_segments)

        line_segments = LineSegments(
            parent=ndb.Key(Room, room_key),
            xs=xs,
            ys=ys,
            user=user)
        line_segments.put()

        room = Room.get_by_id(room_key)
        for client_id in room.client_ids:
            channel.send_message(
                client_id, json.dumps([line_segments.GetPoints()]))


application = webapp2.WSGIApplication([
        ('/', Canvas),
        ('/lines', LinesHandler),
], debug=True)
