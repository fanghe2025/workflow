# Troubleshooting Guide

## Common Errors and Solutions

### ❌ Error: `b'LOGIN failed.'`

This error means the IMAP authentication failed. Follow these steps:

#### Step 1: Enable IMAP in Outlook

1. Go to https://outlook.live.com/mail
2. Click the **gear icon** (⚙️) in the top right corner
3. Click **View all Outlook settings** at the bottom
4. Go to **Mail** > **Sync email**
5. Under **"IMAP access"**, toggle it **ON**
6. Click **Save**
7. Wait 5-10 minutes for the settings to take effect

#### Step 2: Generate an App Password

Even if you don't have 2FA enabled, some Outlook accounts require App Passwords for IMAP:

1. Go to https://account.microsoft.com/security
2. Sign in with your Microsoft account
3. Scroll down to **"App passwords"** section
4. Click **"Create a new app password"**
5. Give it a name (e.g., "Email Workflow Script")
6. Click **Generate**
7. **Copy the 16-character password** (you won't see it again!)
8. Use this password in your `config/imap_config.json` file

**Important**: Use the App Password, NOT your regular Outlook password!

#### Step 3: Verify Your Configuration

Check your `config/imap_config.json`:

```json
{
  "imap_server": "outlook.office365.com",
  "imap_port": 993,
  "smtp_server": "smtp.office365.com",
  "smtp_port": 587,
  "use_tls": true,
  "username": "your-email@outlook.com",
  "password": "your-app-password-here"  ← Use App Password!
}
```

#### Step 4: Test Again

```bash
python scripts/imap_email_reader.py --limit 1
```

### Still Not Working?

1. **Check if IMAP is actually enabled**:
   - Try accessing your Outlook account from a third-party email client
   - If that doesn't work, IMAP might not be enabled

2. **Office 365 Business/Enterprise accounts**:
   - Your IT administrator may have disabled IMAP
   - Contact your IT department to enable IMAP access

3. **Account security settings**:
   - Some accounts have additional security restrictions
   - Check your Microsoft account security settings
   - You may need to allow "less secure app access" (if available)

4. **Try a different approach**:
   - Some accounts work better with different authentication methods
   - Consider using OAuth2 if App Passwords don't work

### Other Common Errors

#### Connection Timeout

- Check your internet connection
- Verify firewall isn't blocking port 993
- Try from a different network

#### SSL/TLS Errors

- Ensure `use_tls` is set to `true` in config
- Verify you're using port 993 (not 143)

#### "No emails found"

- This might be normal if your inbox is empty
- Try checking a different folder: `--folder "Sent"`

## Getting Help

If none of these solutions work:

1. Check the full error message for specific details
2. Verify your Outlook account works in the web interface
3. Try generating a new App Password
4. Check Microsoft account security settings for any blocks
