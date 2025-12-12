import smtplib
from email.message import EmailMessage
from flask import current_app

def send_verification_email(to_email, code):
    msg = EmailMessage()
    msg['Subject'] = 'CodeDiff Verification Code'
    msg['From'] = current_app.config['MAIL_USERNAME']
    msg['To'] = to_email

    # Plain text fallback
    msg.set_content(f"""
    Welcome to CodeDiff!
    
    Your verification code is: {code}
    
    This code will expire in 10 minutes.
    
    If you did not request this, please ignore this email.
    """)

    # HTML Version
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      background-color: #f6f8fa;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 8px;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
      overflow: hidden;
    }}
    .header {{
      background-color: #24292f;
      padding: 24px;
      text-align: center;
    }}
    .header h1 {{
      color: #ffffff;
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }}
    .content {{
      padding: 40px 32px;
      text-align: center;
      color: #24292f;
    }}
    .code-box {{
      background-color: #f6f8fa;
      border: 1px solid #d0d7de;
      border-radius: 6px;
      padding: 16px;
      margin: 24px 0;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 32px;
      font-weight: 700;
      letter-spacing: 4px;
      color: #0969da;
    }}
    .footer {{
      padding: 24px;
      text-align: center;
      font-size: 12px;
      color: #6e7781;
      border-top: 1px solid #d0d7de;
      background-color: #fcfcfc;
    }}
    p {{
      margin: 16px 0;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>CodeDiff</h1>
    </div>
    <div class="content">
      <h2 style="margin-top: 0; font-weight: 500;">Verify your email address</h2>
      <p>Thanks for starting your CodeDiff registration. Here is your verification code:</p>
      <div class="code-box">
        {code}
      </div>
      <p style="color: #57606a; font-size: 14px;">
        This code will expire in 10 minutes.<br>
        If you did not make this request, please ignore this email.
      </p>
    </div>
    <div class="footer">
      &copy; {current_app.config.get('YEAR', '2025')} CodeDiff. All rights reserved.
    </div>
  </div>
</body>
</html>
    """
    
    msg.add_alternative(html_content, subtype='html')
    
    try:
        # Connect to SMTP server
        server_host = current_app.config['MAIL_SERVER']
        server_port = current_app.config['MAIL_PORT']
        use_tls = current_app.config['MAIL_USE_TLS']
        username = current_app.config['MAIL_USERNAME']
        password = current_app.config['MAIL_PASSWORD']
        
        if use_tls:
            with smtplib.SMTP_SSL(server_host, server_port) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server_host, server_port) as smtp:
                if username and password:
                    smtp.starttls()
                    smtp.login(username, password)
                smtp.send_message(msg)
                
        current_app.logger.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False
