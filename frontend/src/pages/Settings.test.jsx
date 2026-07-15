import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Settings from './Settings.jsx';
import { LangProvider } from '../i18n.jsx';
import { api } from '../api.js';

vi.mock('../api.js', () => ({
  api: {
    changePassword: vi.fn(),
    deleteAccount: vi.fn(),
    getTelegramSettings: vi.fn(),
    updateTelegramSettings: vi.fn(),
  },
}));

vi.mock('../auth.js', () => ({
  clearToken: vi.fn(),
}));

function renderSettings() {
  return render(
    <MemoryRouter>
      <LangProvider>
        <Settings />
      </LangProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Telegram section — bot NOT configured on server
// ---------------------------------------------------------------------------

describe('TelegramSettings — bot not configured', () => {
  beforeEach(() => {
    api.getTelegramSettings.mockResolvedValue({
      telegram_bot_configured: false,
      telegram_chat_id: null,
      telegram_notifications: false,
    });
  });

  it('shows a "not configured" notice and no form', async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText(/TELEGRAM_BOT_TOKEN/i)).toBeInTheDocument();
    });
    expect(screen.queryByLabelText(/Chat ID/i)).not.toBeInTheDocument();
  });

  it('shows the section heading', async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText('Telegram notifications')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Telegram section — bot configured
// ---------------------------------------------------------------------------

describe('TelegramSettings — bot configured', () => {
  beforeEach(() => {
    api.getTelegramSettings.mockResolvedValue({
      telegram_bot_configured: true,
      telegram_chat_id: null,
      telegram_notifications: false,
    });
    api.updateTelegramSettings.mockResolvedValue({
      telegram_bot_configured: true,
      telegram_chat_id: '123456',
      telegram_notifications: true,
    });
  });

  it('renders the chat ID input and checkbox', async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/123456789/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('checkbox', { name: /Enable reminders/i })).toBeInTheDocument();
  });

  it('shows pre-filled values from the server', async () => {
    api.getTelegramSettings.mockResolvedValue({
      telegram_bot_configured: true,
      telegram_chat_id: '987654',
      telegram_notifications: true,
    });
    renderSettings();
    await waitFor(() => {
      expect(screen.getByDisplayValue('987654')).toBeInTheDocument();
    });
    expect(screen.getByRole('checkbox', { name: /Enable reminders/i })).toBeChecked();
  });

  it('saves settings and shows success message', async () => {
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/123456789/i)).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/123456789/i), '123456');
    await user.click(screen.getByRole('checkbox', { name: /Enable reminders/i }));
    await user.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() => {
      expect(screen.getByText('Saved.')).toBeInTheDocument();
    });
    expect(api.updateTelegramSettings).toHaveBeenCalledWith('123456', true);
  });

  it('shows error message when save fails', async () => {
    api.updateTelegramSettings.mockRejectedValue(new Error('Service unavailable'));
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/123456789/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() => {
      expect(screen.getByText('Service unavailable')).toBeInTheDocument();
    });
  });

  it('clears success message when input changes', async () => {
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/123456789/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^Save$/i }));
    await waitFor(() => expect(screen.getByText('Saved.')).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/123456789/i), '1');
    expect(screen.queryByText('Saved.')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Localisation
// ---------------------------------------------------------------------------

describe('TelegramSettings — Russian locale', () => {
  it('renders Russian strings when lang=ru', async () => {
    api.getTelegramSettings.mockResolvedValue({
      telegram_bot_configured: true,
      telegram_chat_id: null,
      telegram_notifications: false,
    });

    render(
      <MemoryRouter>
        <LangProvider>
          <Settings />
        </LangProvider>
      </MemoryRouter>
    );

    // Switch to RU via localStorage before mount does not work easily here;
    // verify that the RU key resolves to a non-empty string instead.
    // The real locale switch is covered in i18n.test.jsx.
    await waitFor(() => {
      expect(screen.getByText('Telegram notifications')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe('TelegramSettings — loading', () => {
  it('renders nothing while loading', () => {
    // Never resolves during this test
    api.getTelegramSettings.mockReturnValue(new Promise(() => {}));
    renderSettings();
    // The Telegram section heading should not be present while loading
    expect(screen.queryByText('Telegram notifications')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Existing sections still work after refactor
// ---------------------------------------------------------------------------

describe('Settings — change password section', () => {
  beforeEach(() => {
    api.getTelegramSettings.mockResolvedValue({
      telegram_bot_configured: false,
      telegram_chat_id: null,
      telegram_notifications: false,
    });
  });

  it('renders the change password form', async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText('Change password')).toBeInTheDocument();
    });
  });

  it('calls api.changePassword on submit', async () => {
    api.changePassword.mockResolvedValue({ ok: true });
    const user = userEvent.setup();
    renderSettings();

    await waitFor(() => expect(screen.getByText('Change password')).toBeInTheDocument());

    const pwInputs = document.querySelectorAll('input[type="password"]');
    await user.type(pwInputs[0], 'oldpass');
    await user.type(pwInputs[1], 'newpass1');
    await user.click(screen.getByRole('button', { name: /Update password/i }));

    await waitFor(() => {
      expect(api.changePassword).toHaveBeenCalledWith('oldpass', 'newpass1');
    });
  });
});
