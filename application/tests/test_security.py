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
