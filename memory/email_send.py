"""每日日报 SMTP 发送：定位当日 .docx，作为附件发送。失败即抛。"""

import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from core.paths import SCHE_TASKS, TEMP
from memory.email_config import load_email_config
DONE = str(SCHE_TASKS / "done")
SENT = str(TEMP / "email_report.sent")
EMAIL_LOG = str(TEMP / "email_report.log")


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _today_docx(done_dir: str, today: str) -> str:
    hits = sorted(
        n for n in os.listdir(done_dir)
        if n.startswith(today) and n.endswith('.docx')
    )
    if not hits:
        raise FileNotFoundError(
            f"{done_dir} 中没有 {today} 开头的 .docx（请先生成日报）"
        )
    return os.path.join(done_dir, hits[0])


def _is_fallback_docx(path: str) -> bool:
    return '_fallback' in os.path.basename(path)


def _build(cfg: dict, docx_path: str, date: str) -> EmailMessage:
    msg = EmailMessage()
    subject = cfg['subject'].format(date=date)
    body = cfg['body'].format(date=date)
    if _is_fallback_docx(docx_path):
        subject = f'[兜底] {subject}'
        body = (
            '⚠️ 当日正常日报未生成，以下是兜底版本（最近一份日报）。\n\n'
            + body
        )
    msg['Subject'] = subject
    msg['From'] = f"{cfg.get('sender_name', '')} <{cfg['smtp_user']}>"
    msg['To'] = ', '.join(cfg['to_addrs'])
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=cfg['smtp_user'].split('@', 1)[1])
    msg.set_content(body)
    with open(docx_path, 'rb') as f:
        data = f.read()
    msg.add_attachment(
        data,
        maintype='application',
        subtype='vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename=os.path.basename(docx_path),
    )
    return msg


def _already_sent(today: str, sent_path: str) -> bool:
    if not os.path.exists(sent_path):
        return False
    try:
        with open(sent_path, encoding='utf-8') as f:
            line = f.readline().strip()
        return line.startswith(today)
    except OSError:
        return False


def _audit(today: str, status: str, docx_path: str = '', err: str = '') -> None:
    """写审计行（失败不抛——审计是辅助，发送主流程不受影响）。"""
    try:
        os.makedirs(os.path.dirname(EMAIL_LOG), exist_ok=True)
        with open(EMAIL_LOG, 'a', encoding='utf-8') as f:
            docx = os.path.basename(docx_path) if docx_path else '-'
            f.write(
                f'{datetime.now().isoformat(timespec="seconds")} '
                f'{today} {status} {docx} {err}\n'
            )
    except OSError:
        pass


def send_email(done_dir: str = DONE, today: str = None, sent_path: str = SENT) -> str:
    """发日报邮件。幂等：当天发过抛 RuntimeError。

    Raises:
        ValueError: 配置缺失/不合法（来自 email_config.load_email_config）。
        FileNotFoundError: 当日 .docx 不在 done_dir。
        RuntimeError: 当天已发过 或 SMTP 失败。
    """
    today = today or _today()

    cfg = load_email_config()  # 缺配置/不合法抛 ValueError

    if _already_sent(today, sent_path):
        raise RuntimeError(f'当天已发过日报 ({today})，跳过')

    docx_path = _today_docx(done_dir, today)
    email_msg = _build(cfg, docx_path, today)

    timeout = cfg.get('smtp_timeout', 30)
    try:
        if cfg.get('smtp_use_ssl', True):
            with smtplib.SMTP_SSL(
                cfg['smtp_host'], cfg['smtp_port'], timeout=timeout
            ) as s:
                s.login(cfg['smtp_user'], cfg['smtp_pass'])
                s.send_message(email_msg)
        else:
            with smtplib.SMTP(
                cfg['smtp_host'], cfg['smtp_port'], timeout=timeout
            ) as s:
                s.starttls()
                s.login(cfg['smtp_user'], cfg['smtp_pass'])
                s.send_message(email_msg)
    except (smtplib.SMTPException, OSError) as exc:
        _audit(today, 'FAIL', docx_path, str(exc))
        raise RuntimeError(f'SMTP 失败: {exc}') from exc

    os.makedirs(os.path.dirname(sent_path), exist_ok=True)
    tmp = sent_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(f'{today} {os.path.basename(docx_path)}\n')
    os.replace(tmp, sent_path)
    _audit(today, 'OK', docx_path, '')
    return (
        f'已发送 {os.path.basename(docx_path)} → '
        f'{", ".join(cfg["to_addrs"])}'
    )


if __name__ == '__main__':
    try:
        print(send_email())
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)