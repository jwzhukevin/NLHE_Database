import unittest
from app import app, db, Movie, User

class WatchlistTestCase(unittest.TestCase):

    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        
        app.config.update(
            TESTING=True,
            SECRET_KEY='dev',
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,  # 添加此项
            WTF_CSRF_ENABLED=False
        )
        db.create_all()
        user = User(name='Test', username='test')
        user.set_password('123')
        movie = Movie(title='Test Movie', year='2022')
        db.session.add_all([user, movie])
        db.session.commit()

        self.client = app.test_client()
        self.runner = app.test_cli_runner()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self):
        return self.client.post('/login', data=dict(
            username='test',
            password='123'
        ), follow_redirects=True)

    def test_add_item(self):
        # 登录验证
        login_resp = self.client.post('/login', data={
            'username': 'test',
            'password': '123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        
        # 提交新电影
        add_resp = self.client.post('/add', data={
            'title': 'Test Movie 2023',
            'year': '2023'  # 确保年份是4位数字
        }, follow_redirects=True)
        
        # 打印响应内容调试
        print(add_resp.get_data(as_text=True))
        
        # 验证闪存消息出现在首页
        self.assertIn('Item created.', add_resp.get_data(as_text=True))
        # 验证电影出现在列表
        self.assertIn('Test Movie 2023', add_resp.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main()