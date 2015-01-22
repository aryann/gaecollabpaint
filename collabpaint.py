import constants
import random
import os
import httplib
import jinja2
import json
import webapp2

from google.appengine.api import channel
from google.appengine.api import users
from google.appengine.ext import ndb

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def GenerateClientId(room_name):
    return str(random.randrange(- 2 ** 63, 2 ** 63 - 1)) + '-' + room_name


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


class Home(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        # TODO(aryann): This will not scale as the number of rooms
        # increases.
        room_names = []
        for r in Room.query().fetch():
            room_names.append(r.key.string_id())

        template_values = {
            'room_names': room_names,
        }
        template = JINJA_ENVIRONMENT.get_template('home.html')
        self.response.write(template.render(template_values))


class Canvas(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        room_key = self.request.get('room_key')
        if not room_key:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('Missing query parameter "room_key".')
            self.response.set_status(httplib.BAD_REQUEST)
            return

        room = Room.get_or_insert(room_key)
        client_id = GenerateClientId(room_key)
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
        client_id = self.request.get('client_id')

        # The following snippet breaks up the sending of the initial
        # data, so that we do not exceed the message length limits of
        # the channel.
        lines = []
        payload = None
        for line_segment in LineSegments.GetLineSegmentsForRoom(
            room_key).fetch():
            lines.append(line_segment.GetPoints())
            new_payload = json.dumps(lines)
            if len(new_payload) > channel.MAXIMUM_MESSAGE_LENGTH and payload:
                channel.send_message(client_id, payload)
                payload = None
                lines = [lines[-1]]
            else:
                payload = new_payload

        if payload:
            channel.send_message(client_id, payload)

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


class ChannelConnected(webapp2.RequestHandler):

    def post(self):
        pass


class ChannelDisconnected(webapp2.RequestHandler):

    def post(self):
        client_id = self.request.get('from')
        room_key = client_id.split('-', 1)[1]
        room = Room.get_by_id(room_key)
        room.client_ids.remove(client_id)
        room.put()


application = webapp2.WSGIApplication([
        ('/', Home),
        ('/room', Canvas),
        ('/lines', LinesHandler),
        ('/_ah/channel/connected/', ChannelConnected),
        ('/_ah/channel/disconnected/', ChannelDisconnected),
])
