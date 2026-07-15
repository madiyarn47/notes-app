import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { clearToken } from '../auth.js';
import { useLang } from '../i18n.jsx';

function TelegramSettings() {
  const { t } = useLang();

  const [loading, setLoading] = useState(true);
  const [botConfigured, setBotConfigured] = useState(false);
  const [chatId, setChatId] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getTelegramSettings().then((data) => {
      if (cancelled) return;
      setBotConfigured(data.telegram_bot_configured);
      setChatId(data.telegram_chat_id ?? '');
      setEnabled(data.telegram_notifications);
      setLoading(false);
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      const data = await api.updateTelegramSettings(chatId, enabled);
      setChatId(data.telegram_chat_id ?? '');
      setEnabled(data.telegram_notifications);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return null;

  if (!botConfigured) {
    return (
      <section className="settings-card">
        <h2>{t('telegram.title')}</h2>
        <p className="settings-hint">{t('telegram.notConfigured')}</p>
      </section>
    );
  }

  return (
    <section className="settings-card">
      <h2>{t('telegram.title')}</h2>
      <p className="settings-hint">{t('telegram.hint')}</p>
      <form onSubmit={save}>
        <label>
          {t('telegram.chatIdLabel')}
          <input
            type="text"
            value={chatId}
            onChange={(e) => { setChatId(e.target.value); setSaved(false); }}
            placeholder={t('telegram.chatIdPlaceholder')}
            maxLength={32}
          />
        </label>
        <p className="settings-hint">{t('telegram.chatIdHint')}</p>
        <label className="settings-toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => { setEnabled(e.target.checked); setSaved(false); }}
          />
          {t('telegram.enabledLabel')}
        </label>
        {error && <div className="error">{error}</div>}
        {saved && <div className="success">{t('telegram.saved')}</div>}
        <button type="submit" className="btn btn-primary">{t('telegram.submit')}</button>
      </form>
    </section>
  );
}

export default function Settings() {
  const { t } = useLang();
  const navigate = useNavigate();

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [pwError, setPwError] = useState(null);
  const [pwOk, setPwOk] = useState(false);

  const [deletePw, setDeletePw] = useState('');
  const [deleteError, setDeleteError] = useState(null);

  const changePassword = async (e) => {
    e.preventDefault();
    setPwError(null);
    setPwOk(false);
    try {
      await api.changePassword(currentPw, newPw);
      setPwOk(true);
      setCurrentPw('');
      setNewPw('');
    } catch (err) {
      setPwError(err.message);
    }
  };

  const deleteAccount = async (e) => {
    e.preventDefault();
    setDeleteError(null);
    if (!window.confirm(t('settings.confirmDelete'))) return;
    try {
      await api.deleteAccount(deletePw);
      clearToken();
      navigate('/login', { replace: true });
    } catch (err) {
      setDeleteError(err.message);
    }
  };

  return (
    <div className="settings-page">
      <h1>{t('settings.title')}</h1>

      <section className="settings-card">
        <h2>{t('settings.changePasswordTitle')}</h2>
        <form onSubmit={changePassword}>
          <label>
            {t('settings.currentPassword')}
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            {t('settings.newPassword')}
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              minLength={6}
              autoComplete="new-password"
            />
          </label>
          {pwError && <div className="error">{pwError}</div>}
          {pwOk && <div className="success">{t('settings.passwordChanged')}</div>}
          <button type="submit" className="btn btn-primary">{t('settings.submit')}</button>
        </form>
      </section>

      <TelegramSettings />

      <section className="settings-card danger">
        <h2>{t('settings.dangerZone')}</h2>
        <h3>{t('settings.deleteAccountTitle')}</h3>
        <p className="settings-hint">{t('settings.deleteAccountHint')}</p>
        <form onSubmit={deleteAccount}>
          <label>
            {t('settings.confirmPassword')}
            <input
              type="password"
              value={deletePw}
              onChange={(e) => setDeletePw(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {deleteError && <div className="error">{deleteError}</div>}
          <button type="submit" className="btn btn-danger">{t('settings.deleteAccount')}</button>
        </form>
      </section>
    </div>
  );
}
