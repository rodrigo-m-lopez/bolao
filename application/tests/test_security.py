"""Security tests: open redirect, XSS, CSRF."""
import pytest
import application.app as app_module
from application.app import is_safe_url


class TestIsafeUrl:
    def test_relative_path_is_safe(self, flask_app):
        with flask_app.test_request_context('/'):
            assert is_safe_url('/lista_bolao') is True

    def test_same_host_absolute_is_safe(self, flask_app):
        with flask_app.test_request_context('/'):
            assert is_safe_url('http://localhost/lista_bolao') is True

    def test_external_http_blocked(self, flask_app):
        with flask_app.test_request_context('/'):
            assert is_safe_url('http://evil.com/steal') is False

    def test_external_https_blocked(self, flask_app):
        with flask_app.test_request_context('/'):
            assert is_safe_url('https://attacker.com/') is False

    def test_protocol_relative_blocked(self, flask_app):
        with flask_app.test_request_context('/'):
            assert is_safe_url('//evil.com') is False

    def test_none_input(self, flask_app):
        with flask_app.test_request_context('/'):
            # None passed directly should be handled (safe_next uses request.args)
            assert is_safe_url('') is True  # empty is relative to root

    def test_data_uri_blocked(self, flask_app):
        with flask_app.test_request_context('/'):
            assert is_safe_url('javascript:alert(1)') is False


class TestLogoutRedirect:
    def test_logout_without_next_redirects_to_intro(self, client):
        rv = client.get('/logout', follow_redirects=False)
        assert rv.status_code == 302
        assert '/intro' in rv.headers['Location']

    def test_logout_safe_internal_next(self, client):
        rv = client.get('/logout?next=/lista_bolao', follow_redirects=False)
        assert rv.status_code == 302
        assert '/lista_bolao' in rv.headers['Location']
        assert 'evil' not in rv.headers['Location']

    def test_logout_blocks_external_redirect(self, client):
        rv = client.get('/logout?next=http://evil.com', follow_redirects=False)
        assert rv.status_code == 302
        location = rv.headers['Location']
        assert 'evil.com' not in location
        # Should redirect to the default 'intro' page
        assert '/intro' in location


class TestXss:
    def test_valida_nome_aposta_escapes_html(self, client):
        """Nome de aposta com HTML não deve ser refletido cru."""
        # Need to create a bolao first and set a cookie for session
        db = __import__('application.app', fromlist=['tbl_bolao']).tbl_bolao
        from bson import ObjectId
        db.insert_one({'nome': 'xss_bolao', 'usuario': ObjectId(), 'valor': 10,
                       'premiacao': '', 'descricao': ''})
        # Insert a conflicting aposta
        tbl_aposta = __import__('application.app', fromlist=['tbl_aposta']).tbl_aposta
        tbl_bolao = __import__('application.app', fromlist=['tbl_bolao']).tbl_bolao
        id_bolao = tbl_bolao.find_one({'nome': 'xss_bolao'})['_id']
        tbl_aposta.insert_one({'nome': '<script>alert(1)</script>', 'bolao': id_bolao,
                               'usuario': ObjectId(), 'pago': False})
        rv = client.post('/xss_bolao/valida_nome_aposta',
                         data={'nome_aposta': '<script>alert(1)</script>'})
        assert rv.status_code == 200
        # The raw script tag should be escaped
        assert b'<script>alert(1)</script>' not in rv.data
        assert b'&lt;script&gt;' in rv.data

    def test_valida_nome_bolao_escapes_html(self, client):
        """Nome de bolão com HTML não deve ser refletido cru."""
        import application.app as app_module
        from bson import ObjectId
        app_module.tbl_bolao.insert_one({'nome': '<img src=x>', 'usuario': ObjectId(),
                                         'valor': 10, 'premiacao': '', 'descricao': ''})
        rv = client.post('/valida_nome_bolao', data={'nome_bolao': '<img src=x>'})
        assert rv.status_code == 200
        assert b'<img src=x>' not in rv.data
        assert b'&lt;img' in rv.data


class TestLoginRedirect:
    def test_login_stores_safe_next_in_session(self, client):
        with client.session_transaction() as sess:
            pass  # clear session
        client.get('/login?next=/lista_bolao')
        with client.session_transaction() as sess:
            assert sess.get('next') == '/lista_bolao'

    def test_login_blocks_external_next(self, client):
        client.get('/login?next=http://evil.com/steal')
        with client.session_transaction() as sess:
            # Should fall back to default, not the external URL
            stored = sess.get('next', '')
            assert 'evil.com' not in stored
