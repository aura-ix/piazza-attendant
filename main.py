from dataclasses import dataclass
import sys
from datetime import datetime, timedelta, timezone
import dateutil
import time
import textwrap
import math
import dateutil.parser
import requests
from piazza_api import Piazza
import tomllib
from getpass import getpass

# parse config file location
config_path = 'piazza.toml'
if len(sys.argv) == 2:
  config_path = sys.argv[1]
elif len(sys.argv) > 2:
  print(f'usage: {sys.argv[0]} [configuration_file_path]')
  exit(1)

config = {}
with open(config_path, 'rb') as f:
  config = tomllib.load(f)

if not 'password' in config:
  config['password'] = getpass()

schema = {
  'email': str,
  'password': str,
  'notify-message': str,
  'webhook-url': str,
  'course-id': str,
  'check-interval-minutes': int,
  'notify-min-age-minutes': int,
  'notify-max-age-minutes': int,
}

missing_keys = set(schema).difference(config.keys())
if len(missing_keys) != 0:
  print(f'missing configuration keys: {', '.join(missing_keys)}')
  exit(1)

for key, value in config.items():
  if not type(value) is schema[key]:
    print(f'{key} must be of type {schema[key].__name__}')
    exit(1)

min_threshold = timedelta(0, 60*config['notify-min-age-minutes'])
max_threshold = timedelta(0, 60*config['notify-max-age-minutes'])

# converts a timedelta to a XXdXXhXXm string
def delta_to_str(d):
  total_min = math.floor(d / timedelta(minutes=1))
  mins = total_min % 60
  hours = (total_min // 60) % 24
  days = (total_min // (60*24))

  s = f'{mins}m'
  if hours > 0:
    s = f'{hours}h{s}'
  if days > 0:
    s = f'{days}d{s}'
  return s

@dataclass
class PendingPost:
  Question = "question"
  Followup = "followup"

  kind: str
  id: str
  subject: str
  creation_time: datetime
  modified_time: datetime
  post_num: int
  course_id: str

  def link(self):
    return f'https://piazza.com/class/{self.course_id}/post/{self.post_num}'

  def describe_pending(self, now):
    age_string = ''
    create_age = delta_to_str(now - self.creation_time)
    modify_age = delta_to_str(now - self.modified_time)
    if create_age == modify_age:
      age_string = f'(created {create_age} ago)'
    else:
      age_string = f'(created {create_age} ago, updated {modify_age} ago)'
    return f'Unanswered {self.kind}: [{textwrap.shorten(self.subject, width=80, placeholder='...')}](<{self.link()}>) {age_string}'

def get_post(course, cid):
  time.sleep(1)
  return course.get_post(cid)

def check_pending(course):
  feed = course.get_feed(limit=999999, offset=0)
  check_time = datetime.now(timezone.utc)
  pending = []
  for post in feed['feed']:
    # check if post is unanswered question
    if post['type'] == 'question' and post['no_answer'] != 0:
      post_detail = get_post(course, post['id'])
      post_time = dateutil.parser.parse(post_detail['created'])
      modify_time = dateutil.parser.parse(post['modified'])

      if post_time + min_threshold < check_time:
        pending.append(PendingPost(
          PendingPost.Question,
          post['id'],
          post['subject'],
          post_time,
          modify_time,
          post['nr'],
          course._nid,
        ))

    # check for unanswered followups
    if post['no_answer_followup'] > 0:
      post_detail = get_post(course, post['id'])
      for child in post_detail['children']:
        if 'no_answer' in child and child['no_answer'] != 0:
          followup_time = dateutil.parser.parse(child['created'])
          modify_time = dateutil.parser.parse(child['updated'])
          if followup_time + min_threshold < check_time:
            pending.append(PendingPost(
              PendingPost.Followup,
              child['id'],
              child['subject'],
              followup_time,
              modify_time,
              post['nr'],
              course._nid,
            ))
  return pending

def send_pending_summary(pending):
  # nothing to report if there are no pending messages
  if len(pending) <= 0:
    return
  
  current_time = datetime.now(timezone.utc)

  # newest first
  pending.sort(key=lambda x: x.creation_time, reverse=True)

  # ping if there are any messages within our time threshold
  msg = ""
  for p in pending:
    if p.modified_time + max_threshold > current_time:
      msg += config['notify-message'] + '\n'
      break

  # maximum webhook message length
  max_len = 1950

  list_count = 0
  for p in pending:
    txt = f'- {p.describe_pending(current_time)}\n'
    if len(txt) + len(msg) > max_len:
      break
    msg += txt
    list_count += 1

  if list_count != len(pending):
    msg += f'*({len(pending) - list_count} more...)*'

  max_len = 2000 - 3
  requests.post(config['webhook-url'], json={
    "username": 'Piazza',
    "content": msg[:max_len] + (msg[max_len:] and '...')
  })

def check_loop(course):
  while True:
    print("checking for pending posts...")
    pending = check_pending(course)
    print(f'{len(pending)} pending posts found')
    send_pending_summary(pending)
    time.sleep(config['check-interval-minutes'] * 60)

p = Piazza()
p.user_login(email=config['email'], password=config['password'])
course = p.network(config['course-id'])
check_loop(course)