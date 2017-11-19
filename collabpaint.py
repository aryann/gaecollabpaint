import constants
import random
import os
import httplib
import jinja2
import re
import string
import webapp2

ROOM_KEY_RE = r'^[a-f0-9]{16}$'
ROOM_KEY_ALPHABET = 'abcdef' + string.digits
ROOM_KEY_LENGTH = 16

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def generate_client_id(room_name):
    return str(random.randrange(- 2 ** 63, 2 ** 63 - 1)) + '.' + room_name


def generate_room_key():
    return ''.join(random.choice(ROOM_KEY_ALPHABET)
                   for _ in xrange(ROOM_KEY_LENGTH))


class Canvas(webapp2.RequestHandler):

    def get(self, room_key):
        if not room_key:
            self.redirect('/' + generate_room_key())
            return

        if not re.match(ROOM_KEY_RE, room_key):
            self.response.write("I don't recognize this room.")
            self.response.status = httplib.NOT_FOUND
            return

        template_values = {
            'room_key': room_key,
            'width': constants.WIDTH,
            'height': constants.HEIGHT,
            'url': self.request.url,
        }
        template = JINJA_ENVIRONMENT.get_template('canvas.html')
        self.response.write(template.render(template_values))


application = webapp2.WSGIApplication([
        ('/(?P<room_key>.*)', Canvas),
])
