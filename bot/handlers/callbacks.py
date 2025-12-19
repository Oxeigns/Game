from __future__ import annotations

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from ..services import admin_panel
from ..utils import box_card


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data == "panel:home":
        await query.edit_message_text(admin_panel.panel_main_card(), parse_mode="Markdown", reply_markup=admin_panel.PANEL_BUTTONS)
    elif data == "panel:stats":
        await admin_panel.panel_stats(update, context)
    elif data == "panel:admin":
        await admin_panel.panel_admin(update, context)
    elif data == "panel:broadcast":
        await admin_panel.panel_broadcast(update, context)
    elif data == "panel:logs":
        await admin_panel.panel_logs(update, context)
    elif data == "panel:groups":
        await admin_panel.panel_groups(update, context)
    elif data == "panel:maintenance":
        await admin_panel.panel_maintenance(update, context)
    elif data == "panel:help":
        await admin_panel.panel_help(update, context)
    else:
        await query.edit_message_text(box_card("❓", ["Unknown action", "Next: Use panel buttons"]), parse_mode="Markdown")


CALLBACKS = [CallbackQueryHandler(callback_router)]
