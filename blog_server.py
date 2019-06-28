import redis
from datetime import datetime

from flask import Flask
from flask import render_template
from flask import session
from flask import request
from flask import url_for
from flask import g
from flask import redirect

app = Flask(__name__)
app.secret_key = 'Wt\n\x90(\x8d\x1f\xde}\xdb\x88\xe5\xaf\xcd\x8c\xcdW\xe5\xb7\xca\xbaJ\xaf\xe8'


def init_DB():
  db = redis.StrictRedis(
    host='localhost',
    port=6379,
    db=0
  )
  return db


@app.before_request
def before_request():
  g.redis_db = init_DB()


@app.route('/signup', methods=['GET', 'POST'])
def signup():
  error = None
  if session:
    return redirect(url_for('home'))
  if request.method == 'GET':
    return render_template('signup.html', error=error)
  username = request.form['username']
  password = request.form['password']
  user_id = str(g.redis_db.incrby('next_user_id', 1000))
  print("sign up  ", user_id)
  g.redis_db.hmset('user:' + user_id,
                   dict(username=username, password=password))
  g.redis_db.hset('users', username, user_id)
  session['username'] = username
  return redirect(url_for('home'))


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
  error = None
  if session:
    return redirect(url_for('home'))
  if request.method == 'GET':
    return render_template('login.html', error=error)
  username = request.form['username']
  password = request.form['password']
  user_id = str(g.redis_db.hget('users', username))
  if not user_id:
    error = 'No such user'
    return render_template('login.html', error=error)

  user_password = str(g.redis_db.hget('user:' + str(user_id), 'password'))
  if user_password != password:
    error = 'Incorrect password'
    return render_template('login.html', error=error)

  session['username'] = username
  return redirect(url_for('home'))


@app.route('/logout', methods=['GET'])
def logout():
  session.pop('username', None)
  return redirect(url_for('login'))


def _get_timeline(user_id):
  posts = g.redis_db.lrange('timeline:' + str(user_id), 0, -1)
  timeline = []
  for post_id in posts:
    print(str(post_id.decode('utf-8')))
    post = g.redis_db.hgetall('post:' + str(post_id.decode('utf-8')))
    print(post)
    timeline.append(dict(
      username=g.redis_db.hget('user:' + str(user_id),
                               'username').decode('utf-8'),
      ts=post[b'ts'].decode('utf-8'),
      text=post[b'text'].decode('utf-8'),
      post_id=post_id.decode('utf-8')))
  return timeline


def _get_all_timeline():
  all_users = g.redis_db.hgetall('users')
  print("all users  ", all_users)
  all_posts = []
  for user in all_users:
    posts = g.redis_db.lrange('timeline:' + str(all_users[user].decode('utf-8')), 0, -1)
    if len(posts):
      all_posts.append(posts)
  print(all_posts)
  timeline = []
  for user_posts in all_posts:
    for post_id in user_posts:
      post = g.redis_db.hgetall('post:' + str(post_id.decode('utf-8')))
      print(post)
      timeline.append(dict(
        username=g.redis_db.hget('user:' + str(post[b'user_id'].decode('utf-8')),
                                 'username').decode('utf-8'),
        ts=post[b'ts'].decode('utf-8'),
        text=post[b'text'].decode('utf-8'),
        post_id=post_id.decode('utf-8')))
  timeline = reversed(sorted(timeline, key=lambda item: item['ts']))
  return timeline


@app.route('/home', methods=['GET', 'POST'])
def home():
  # g.redis_db.flushdb()
  if not session:
    return redirect(url_for('login'))

  user_id = g.redis_db.hget('users', session['username']).decode('utf-8')
  if request.method == 'GET':
    return render_template('home.html', timeline=_get_all_timeline())

  text = request.form['post']
  post_id = str(g.redis_db.incr('next_post_id'))
  g.redis_db.hmset('post:' + str(post_id), dict(user_id=user_id,
                                     ts=str(datetime.utcnow()), text=text))
  g.redis_db.lpush('timeline:' + str(user_id), str(post_id))
  g.redis_db.ltrim('timeline:' + str(user_id), 0, 100)
  return render_template('home.html', timeline=_get_all_timeline())


@app.route('/my_profile', methods=['GET', 'POST'])
def my_profile():

  if not session:
    return redirect(url_for('login'))

  user_id = g.redis_db.hget('users', session['username']).decode('utf-8')

  if request.method == 'GET':
    return render_template('my_profile.html', timeline=_get_timeline(user_id))

  text = request.form['post']
  post_id = str(g.redis_db.incr('next_post_id'))
  g.redis_db.hmset('post:' + post_id, dict(user_id=user_id,
                                     ts=str(datetime.utcnow()), text=text))
  g.redis_db.lpush('timeline:' + str(user_id), str(post_id))
  g.redis_db.ltrim('timeline:' + str(user_id), 0, 100)
  return render_template('my_profile.html', timeline=_get_timeline(user_id))


@app.route('/delete', methods=['GET'])
def delete():
  post_id = request.args.get('id')
  user_id = g.redis_db.hget('users', session['username'])
  g.redis_db.delete('post:' + str(post_id))

  g.redis_db.lrem('timeline:' + str(user_id.decode('utf-8')), 1, post_id)
  return redirect(url_for('home'))


@app.route('/edit', methods=['GET', 'POST'])
def edit():
  if not session:
    return redirect(url_for('login'))
  user_id = g.redis_db.hget('users', session['username']).decode('utf-8')
  post_id = request.args.get('id')
  if request.method == 'GET':
    post = g.redis_db.hgetall('post:' + str(post_id))
    current_post = dict(
      username=g.redis_db.hget('user:' + str(post[b'user_id'].decode('utf-8')),
                               'username').decode('utf-8'),
      ts=post[b'ts'].decode('utf-8'),
      text=post[b'text'].decode('utf-8'),
      post_id=post_id)
    return render_template('edit.html', post=current_post)
  text = request.form['post']

  g.redis_db.hmset('post:' + str(post_id), dict(user_id=user_id,
                                     ts=str(datetime.utcnow()), text=text))
  return redirect(url_for('detail', id=post_id))


@app.route('/detail', methods=['GET'])
def detail():
  if not session:
    return redirect(url_for('login'))
  post_id = request.args.get('id')
  post = g.redis_db.hgetall('post:' + str(post_id))
  print(post)
  current_post = dict(
        username=g.redis_db.hget('user:' + str(post[b'user_id'].decode('utf-8')),
                                 'username').decode('utf-8'),
        ts=post[b'ts'].decode('utf-8'),
        text=post[b'text'].decode('utf-8'),
        post_id=post_id)
  return render_template('detail.html', post=current_post)


if __name__ == "__main__":
  app.run(debug=True)

