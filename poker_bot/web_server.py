from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from urllib.parse import urlencode
from typing import TypedDict

from aiohttp import ClientSession
from aiohttp import web

from .config import AppConfig
from .game import Action, PokerTable
from .registry import TableRegistry
from .table_renderer import render_table
from .table_views import serialize_viewer_table


logger = logging.getLogger(__name__)
DISCORD_SDK_URL = "https://esm.sh/@discord/embedded-app-sdk@2.5.0/es2022/embedded-app-sdk.bundle.mjs"


class UserSession(TypedDict, total=False):
    user_id: int
    username: str
    avatar: object
    exp: int


def _safe_next_path(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Texas Hold'em Table</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1118;
      --panel: #111b26;
      --line: #26384a;
      --text: #edf4f8;
      --muted: #9fb0bd;
      --gold: #efd074;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #05090d;
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      overflow: hidden;
    }
    .app {
      width: 100vw;
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
    }
    main {
      width: 100%;
      height: 100%;
    }
    .stage {
      position: relative;
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      background: #04080b;
      overflow: hidden;
    }
    .stage img {
      display: block;
      width: min(100vw, calc(100vh * 1.579));
      width: min(100vw, calc(100dvh * 1.579));
      max-width: 100vw;
      max-height: 100vh;
      max-height: 100dvh;
      object-fit: contain;
      filter: drop-shadow(0 26px 60px rgba(0, 0, 0, .48));
    }
    .table-overlay {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }
    .float-window {
      position: absolute;
      z-index: 4;
      pointer-events: auto;
      background: rgba(9, 16, 23, .88);
      border: 1px solid rgba(143, 169, 188, .28);
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 18px 44px rgba(0, 0, 0, .32);
      backdrop-filter: blur(10px);
    }
    .auth-window {
      top: 14px;
      left: max(14px, env(safe-area-inset-left));
      width: min(312px, calc(100vw - 28px));
    }
    .info-window {
      top: 14px;
      right: max(14px, env(safe-area-inset-right));
      width: min(330px, calc(100vw - 28px));
      max-height: min(58vh, 520px);
      overflow: auto;
    }
    .action-window {
      left: 50%;
      bottom: max(14px, env(safe-area-inset-bottom));
      width: min(640px, calc(100vw - 28px));
      transform: translateX(-50%);
    }
    .dealer-window {
      left: max(14px, env(safe-area-inset-left));
      bottom: max(158px, calc(env(safe-area-inset-bottom) + 158px));
      width: min(340px, calc(100vw - 28px));
      max-height: 46vh;
      overflow: auto;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 16px;
      color: var(--gold);
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(82, 104, 123, .25);
      font-size: 14px;
    }
    .seat {
      padding: 10px 0;
      border-bottom: 1px solid rgba(82, 104, 123, .25);
    }
    .seat strong {
      display: block;
      font-size: 15px;
    }
    .seat span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .turn { color: var(--gold); }
    .controls {
      display: grid;
      gap: 10px;
    }
    button, select, input, a.button {
      width: 100%;
      border: 1px solid var(--line);
      background: #172535;
      color: var(--text);
      min-height: 38px;
      padding: 8px 10px;
      font: inherit;
      text-align: center;
      text-decoration: none;
      display: block;
    }
    button, a.button {
      cursor: pointer;
      font-weight: 700;
    }
    button.primary, a.button.primary {
      background: #1c7a52;
      border-color: #35a673;
    }
    button.secondary {
      background: #203246;
      border-color: #4b657e;
    }
    button.danger {
      background: #7c2430;
      border-color: #aa3a4a;
    }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .message {
      color: var(--gold);
      min-height: 18px;
      font-size: 13px;
    }
    .panel-title {
      margin: -2px 0 10px;
      color: var(--gold);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      user-select: none;
    }
    .drag-handle {
      cursor: move;
      touch-action: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .drag-handle::after {
      content: "drag";
      color: var(--muted);
      font-size: 11px;
      font-weight: 400;
      text-transform: none;
    }
    .seat-list {
      display: grid;
      gap: 2px;
    }
    #actionButtons {
      grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
    }
    #raiseAmount {
      max-width: 220px;
      justify-self: center;
    }
    #offlineControls {
      display: grid;
      gap: 8px;
    }
    @media (max-width: 920px) {
      body { overflow: auto; }
      .app {
        min-height: 100vh;
        min-height: 100dvh;
        height: auto;
      }
      .stage {
        min-height: max(100vh, 840px);
        min-height: max(100dvh, 840px);
        align-items: center;
        overflow: visible;
      }
      .stage img {
        width: 100vw;
        max-height: 100vh;
        max-height: 100dvh;
      }
      .auth-window, .info-window, .dealer-window, .action-window {
        left: 12px;
        right: 12px;
        width: auto;
        transform: none;
      }
      .auth-window { top: 12px; }
      .info-window {
        top: auto;
        bottom: 326px;
        max-height: 22vh;
      }
      .dealer-window {
        top: auto;
        bottom: 178px;
        max-height: 24vh;
      }
      .action-window {
        bottom: 12px;
      }
      #actionButtons {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <main>
      <section class="stage">
        <img id="tableImage" alt="Poker table">
        <div class="table-overlay">
          <div class="float-window auth-window controls draggable-window" id="authPanel" data-window-id="auth"></div>

          <div class="float-window info-window draggable-window" data-window-id="info">
            <h2 class="panel-title drag-handle" data-drag-handle>Table Window</h2>
            <div id="facts"></div>
            <h2 class="panel-title drag-handle" style="margin-top:12px" data-drag-handle>Seats</h2>
            <div id="seats" class="seat-list"></div>
            <h2 class="panel-title drag-handle" style="margin-top:12px" data-drag-handle>Last Result</h2>
            <div id="result" class="row">-</div>
          </div>

          <div class="float-window dealer-window controls draggable-window" id="tableControls" data-window-id="tableActions">
            <h2 class="panel-title drag-handle" data-drag-handle>Table Actions</h2>
            <button class="primary" id="startButton" data-table-action="start">Start Hand</button>
            <div class="grid2">
              <input id="seatNumber" type="number" min="1" placeholder="Seat">
              <button data-control-action="seatMove">Move My Seat</button>
            </div>
            <div id="offlineControls">
              <input id="boardCards" placeholder="Board: Ah Kd Qs 7c 2h">
              <button data-control-action="offlineBoard">Set Board</button>
              <select id="cardPlayer"></select>
              <input id="holeCards" placeholder="Player cards: As Ad">
              <button data-control-action="offlineCards">Set Player Cards</button>
              <select id="actor"></select>
              <button data-table-action="showdown">Showdown</button>
              <button data-control-action="manualAward">Manual Award To Selected Player</button>
            </div>
            <div id="message" class="message"></div>
          </div>

          <div class="float-window action-window controls draggable-window" id="playerControls" data-window-id="playerActions">
            <h2 class="panel-title drag-handle" data-drag-handle>Player Actions</h2>
            <div class="row"><span>Your cards</span><strong id="yourCards">-</strong></div>
            <div class="row"><span>Status</span><strong id="yourStatus">Waiting</strong></div>
            <div id="actionButtons" class="controls"></div>
            <input id="raiseAmount" type="number" min="1" placeholder="Raise total">
            <div id="playerMessage" class="message"></div>
          </div>
        </div>
      </section>
    </main>
  </div>
  <script>
    const parts = window.location.pathname.split('/').filter(Boolean);
    const tableId = parts[1];
    const image = document.getElementById('tableImage');
    const facts = document.getElementById('facts');
    const seats = document.getElementById('seats');
    const result = document.getElementById('result');
    const actor = document.getElementById('actor');
    const cardPlayer = document.getElementById('cardPlayer');
    const message = document.getElementById('message');
    const playerMessage = document.getElementById('playerMessage');
    const actionButtons = document.getElementById('actionButtons');
    const tableControls = document.getElementById('tableControls');
    const playerControls = document.getElementById('playerControls');
    const authPanel = document.getElementById('authPanel');
    let latest = null;
    let activityAuthAttempted = false;
    let activityAuthRunning = false;
    let activityAuthFailed = false;

    authPanel.addEventListener('click', event => {
      const target = event.target.closest('[data-auth-action]');
      if (!target) return;
      if (target.dataset.authAction === 'retry') {
        startDiscordActivityAuth(target.dataset.clientId || (latest && latest.activity_client_id) || '');
      }
    });

    const tableFactObjects = [
      { label: 'Game', value: data => `${data.mode.toUpperCase()} Texas Hold'em` },
      { label: 'Phase', value: data => data.phase },
      { label: 'Pot', value: data => data.pot },
      { label: 'Signed in', value: data => data.authenticated ? data.viewer_name : 'Not signed in' },
      { label: 'Blinds', value: data => `${data.small_blind}/${data.big_blind}` },
      { label: 'Current bet', value: data => data.highest_bet },
      { label: 'Board', value: data => data.board.length ? data.board.join(' ') : '-' },
      { label: 'Turn', value: data => data.current_player_name || '-' },
      { label: 'Timeout', value: data => data.seconds_until_timeout === null ? '-' : `${data.seconds_until_timeout}s` },
    ];

    const seatInfoObjects = [
      { className: 'seat-title', value: player => `Seat ${player.seat}: ${player.name}` },
      { value: player => `${player.chips} chips - bet ${player.bet} - committed ${player.committed}` },
      { value: player => `${player.roles.length ? player.roles.join(' / ') + ' - ' : ''}${player.folded ? 'folded' : player.all_in ? 'all-in' : 'active'}` },
      { value: player => `Cards: ${player.hole_cards.length ? player.hole_cards.join(' ') : player.offline_cards.length ? player.offline_cards.join(' ') : '-'}` },
    ];

    const actionObjects = {
      fold: { label: 'Fold', className: 'danger' },
      call: { label: 'Call', className: 'primary' },
      check: { label: 'Check', className: 'primary' },
      raise_to: { label: 'Raise To', className: '' },
      all_in: { label: 'All In', className: 'danger' },
    };

    function setupDraggableWindows() {
      for (const windowElement of document.querySelectorAll('.draggable-window')) {
        const saved = loadWindowPosition(windowElement.dataset.windowId);
        if (saved) applyWindowPosition(windowElement, saved);
        windowElement.addEventListener('pointerdown', startWindowDrag);
      }
    }

    function loadWindowPosition(windowId) {
      if (!windowId) return null;
      try {
        const value = localStorage.getItem(`poker-window-${tableId}-${windowId}`);
        return value ? JSON.parse(value) : null;
      } catch (error) {
        return null;
      }
    }

    function saveWindowPosition(windowElement) {
      const windowId = windowElement.dataset.windowId;
      if (!windowId) return;
      try {
        localStorage.setItem(`poker-window-${tableId}-${windowId}`, JSON.stringify({
          left: windowElement.offsetLeft,
          top: windowElement.offsetTop,
        }));
      } catch (error) {}
    }

    function applyWindowPosition(windowElement, position) {
      windowElement.style.left = `${position.left}px`;
      windowElement.style.top = `${position.top}px`;
      windowElement.style.right = 'auto';
      windowElement.style.bottom = 'auto';
      windowElement.style.transform = 'none';
    }

    function startWindowDrag(event) {
      if (!event.target.closest('[data-drag-handle]')) return;
      const windowElement = event.currentTarget;
      const startX = event.clientX;
      const startY = event.clientY;
      const rect = windowElement.getBoundingClientRect();
      const overlayRect = document.querySelector('.table-overlay').getBoundingClientRect();
      if (windowElement.setPointerCapture) windowElement.setPointerCapture(event.pointerId);
      windowElement.style.right = 'auto';
      windowElement.style.bottom = 'auto';
      windowElement.style.transform = 'none';

      function move(pointerEvent) {
        const nextLeft = rect.left - overlayRect.left + pointerEvent.clientX - startX;
        const nextTop = rect.top - overlayRect.top + pointerEvent.clientY - startY;
        const maxLeft = Math.max(0, overlayRect.width - rect.width);
        const maxTop = Math.max(0, overlayRect.height - rect.height);
        windowElement.style.left = `${Math.min(Math.max(0, nextLeft), maxLeft)}px`;
        windowElement.style.top = `${Math.min(Math.max(0, nextTop), maxTop)}px`;
      }

      function finish() {
        saveWindowPosition(windowElement);
        windowElement.removeEventListener('pointermove', move);
        windowElement.removeEventListener('pointerup', finish);
        windowElement.removeEventListener('pointercancel', finish);
      }

      windowElement.addEventListener('pointermove', move);
      windowElement.addEventListener('pointerup', finish);
      windowElement.addEventListener('pointercancel', finish);
    }

    authPanel.addEventListener('click', event => {
      const target = event.target.closest('[data-auth-action]');
      if (!target) return;
      const action = target.dataset.authAction;
      if (action === 'retry') {
        startDiscordActivityAuth(target.dataset.clientId || (latest && latest.activity_client_id) || '');
      } else if (action === 'join') {
        postJoin();
      } else if (action === 'leave') {
        postLeave();
      }
    });

    tableControls.addEventListener('click', event => {
      const tableAction = event.target.closest('[data-table-action]');
      if (tableAction) {
        postTableAction(tableAction.dataset.tableAction);
        return;
      }
      const control = event.target.closest('[data-control-action]');
      if (!control) return;
      const action = control.dataset.controlAction;
      if (action === 'seatMove') {
        postSeatMove();
      } else if (action === 'offlineBoard') {
        postOfflineBoard();
      } else if (action === 'offlineCards') {
        postOfflineCards();
      } else if (action === 'manualAward') {
        postManualAward();
      }
    });

    actionButtons.addEventListener('click', event => {
      const button = event.target.closest('[data-player-action]');
      if (!button) return;
      postPlayerAction(button.dataset.playerAction);
    });

    function text(value) {
      return value === null || value === undefined || value === '' ? '-' : String(value);
    }

    function html(value) {
      return text(value).replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char]));
    }

    function render(data) {
      latest = data;
      image.src = `/api/tables/${tableId}/image?v=${Date.now()}`;
      renderAuthPanel(data);
      renderFacts(data);
      renderSeats(data.players);
      result.textContent = data.last_result || '-';
      const canControl = data.authenticated && data.viewer_is_seated;
      const showTableControls = canControl && (!data.hand_running || data.mode === 'offline');
      tableControls.style.display = showTableControls ? 'grid' : 'none';
      playerControls.style.display = canControl ? 'grid' : 'none';
      document.getElementById('offlineControls').style.display = canControl && data.mode === 'offline' && data.hand_running ? 'grid' : 'none';
      document.getElementById('startButton').style.display = !data.hand_running && data.can_start_next_hand ? 'block' : 'none';
      updatePlayerSelects(data);
      updatePlayerControls(data);
      if (!data.authenticated && !activityAuthAttempted && data.activity_client_id) {
        startDiscordActivityAuth(data.activity_client_id);
      }
    }

    function renderFacts(data) {
      facts.innerHTML = tableFactObjects.map(field => `
        <div class="row"><span>${html(field.label)}</span><strong>${html(field.value(data))}</strong></div>
      `).join('');
    }

    function renderSeats(players) {
      seats.innerHTML = players.map(player => `
        <div class="seat">
          ${seatInfoObjects.map((field, index) => {
            const content = html(field.value(player));
            return index === 0 ? `<strong>${content}</strong>` : `<span>${content}</span>`;
          }).join('')}
        </div>
      `).join('') || '<div class="row">No players seated</div>';
    }

    function renderAuthPanel(data) {
      if (!data.authenticated) {
        const status = activityAuthRunning
          ? '<div class="message">Authorizing with Discord...</div>'
          : activityAuthFailed
            ? '<div class="message">Discord authorization did not start. Use the Open Poker App button in Discord, not the browser backup link.</div>'
            : '<div class="message">Authorizing with Discord automatically...</div>';
        authPanel.innerHTML = `
          <h2 class="panel-title drag-handle" data-drag-handle>Login</h2>
          ${status}
          <button class="primary" data-auth-action="retry" data-client-id="${html(data.activity_client_id || '')}">Retry Discord Authorization</button>
          <a class="button secondary" href="/">Back to Lobby</a>
          <a class="button secondary" href="/login?next=${encodeURIComponent(location.pathname)}">Browser Backup</a>
          <div id="authMessage" class="message"></div>
        `;
        return;
      }
      if (!data.viewer_is_seated) {
        authPanel.innerHTML = `
          <h2 class="panel-title drag-handle" data-drag-handle>Seat</h2>
          <div class="row"><span>Signed in</span><strong>${html(data.viewer_name)}</strong></div>
          <button class="primary" data-auth-action="join">Join This Table</button>
          <a class="button secondary" href="/">Back to Lobby</a>
          <a class="button secondary" href="/logout?next=${encodeURIComponent(location.pathname)}">Log out</a>
          <div id="authMessage" class="message"></div>
        `;
        return;
      }
      authPanel.innerHTML = `
        <h2 class="panel-title drag-handle" data-drag-handle>Seat</h2>
        <div class="row"><span>Signed in</span><strong>${html(data.viewer_name)}</strong></div>
        <a class="button secondary" href="/">Back to Lobby</a>
        ${data.hand_running ? '' : '<button data-auth-action="leave">Leave Table</button>'}
        <div id="authMessage" class="message"></div>
      `;
    }

    function authMessageTarget() {
      return document.getElementById('authMessage') || message;
    }

    function updatePlayerSelects(data) {
      const options = data.players.map(player => `<option value="${player.user_id}">${player.seat}. ${html(player.name)}</option>`).join('');
      for (const select of [actor, cardPlayer]) {
        const old = select.value;
        select.innerHTML = options;
        if ([...select.options].some(option => option.value === old)) select.value = old;
      }
      if (data.current_user_id) actor.value = String(data.current_user_id);
    }

    function updatePlayerControls(data) {
      actionButtons.innerHTML = '';
      if (!data.authenticated || !data.viewer_is_seated) return;
      const playerId = data.viewer_id;
      const me = data.players.find(player => player.user_id === playerId);
      document.getElementById('raiseAmount').style.display = data.viewer_legal_actions.includes('raise_to') ? 'block' : 'none';
      document.getElementById('yourCards').textContent = me && me.hole_cards.length ? me.hole_cards.join(' ') : '-';
      if (!data.hand_running) {
        document.getElementById('yourStatus').textContent = data.game_over ? 'Game over' : 'Waiting for next hand';
        return;
      }
      if (data.current_user_id !== playerId) {
        document.getElementById('yourStatus').textContent = `Waiting for ${data.current_player_name || 'another player'}`;
        return;
      }
      document.getElementById('yourStatus').textContent = `Your turn - to call ${data.highest_bet - (me ? me.bet : 0)}`;
      for (const action of data.viewer_legal_actions) {
        const definition = actionObjects[action] || { label: action.replace('_', '-'), className: '' };
        const button = document.createElement('button');
        button.textContent = definition.label;
        if (definition.className) button.className = definition.className;
        button.dataset.playerAction = action;
        actionButtons.appendChild(button);
      }
    }

    async function request(path, payload = {}, targetMessage = message) {
      targetMessage.textContent = 'Working...';
      try {
        const response = await fetch(`/api/tables/${tableId}/${path}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const responseText = await response.text();
        let data = {};
        try {
          data = responseText ? JSON.parse(responseText) : {};
        } catch (error) {
          data = { error: responseText };
        }
        if (!response.ok) {
          targetMessage.textContent = data.error || 'Request failed';
          return false;
        }
        targetMessage.textContent = data.message || 'Done';
        await refresh();
        return true;
      } catch (error) {
        targetMessage.textContent = error.message || 'Network request failed';
        return false;
      }
    }

    async function postTableAction(action) {
      await request('action', { action });
    }

    async function postJoin() {
      await request('me/join', {}, authMessageTarget());
    }

    async function postLeave() {
      await request('me/leave', {}, authMessageTarget());
    }

    async function postPlayerAction(action) {
      const payload = { action };
      if (action === 'raise_to') payload.amount = Number(document.getElementById('raiseAmount').value);
      const response = await fetch(`/api/tables/${tableId}/me/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      playerMessage.textContent = response.ok ? data.message || 'Done' : data.error || 'Request failed';
      await refresh();
    }

    async function postSeatMove() {
      await request('seat/move', {
        seat: Number(document.getElementById('seatNumber').value),
      });
    }

    async function postOfflineBoard() {
      await request('offline/board', { cards: document.getElementById('boardCards').value });
    }

    async function postOfflineCards() {
      await request('offline/cards', {
        user_id: Number(cardPlayer.value),
        cards: document.getElementById('holeCards').value,
      });
    }

    async function postManualAward() {
      await request('award', { user_id: Number(actor.value) });
    }

    async function refresh() {
      try {
        const api = `/api/tables/${tableId}`;
        const response = await fetch(api, { cache: 'no-store' });
        if (!response.ok) throw new Error(await response.text());
        render(await response.json());
      } catch (error) {
        result.textContent = error.message;
      }
    }

    async function startDiscordActivityAuth(clientId) {
      if (!clientId || activityAuthRunning) return;
      activityAuthAttempted = true;
      activityAuthRunning = true;
      activityAuthFailed = false;
      renderAuthPanel(latest || { authenticated: false, activity_client_id: clientId });
      try {
        const { DiscordSDK } = await import('/assets/discord-sdk.mjs');
        const discordSdk = new DiscordSDK(clientId);
        await withTimeout(discordSdk.ready(), 10000);
        const { code } = await discordSdk.commands.authorize({
          client_id: clientId,
          response_type: 'code',
          state: '',
          prompt: 'none',
          scope: ['identify'],
        });
        const tokenData = await exchangeDiscordCode(code);
        await discordSdk.commands.authenticate({ access_token: tokenData.access_token });
        activityAuthRunning = false;
        await refresh();
      } catch (error) {
        activityAuthRunning = false;
        activityAuthFailed = true;
        renderAuthPanel(latest || { authenticated: false, activity_client_id: clientId });
      }
    }

    function withTimeout(promise, ms) {
      return Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Discord Activity SDK is not available here')), ms)),
      ]);
    }

    async function exchangeDiscordCode(code) {
      let lastError = null;
      for (const url of ['/.proxy/api/token', '/api/token']) {
        try {
          const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
          });
          const data = await response.json();
          if (response.ok) return data;
          lastError = new Error(data.error || 'Discord token exchange failed');
        } catch (error) {
          lastError = error;
        }
      }
      throw lastError || new Error('Discord token exchange failed');
    }

    setupDraggableWindows();
    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


LOBBY_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Discord Poker</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1118;
      --panel: #111b26;
      --line: #26384a;
      --text: #edf4f8;
      --muted: #9fb0bd;
      --gold: #efd074;
      --green: #1c7a52;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top, #182636 0, var(--bg) 54%);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
    }
    main {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(10, 16, 23, .86);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
    }
    h1 { margin: 0; font-size: 22px; }
    .status {
      color: var(--muted);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 10px;
      white-space: nowrap;
    }
    .content {
      padding: 20px;
      display: grid;
      gap: 14px;
      align-content: start;
      max-width: 980px;
      width: 100%;
      margin: 0 auto;
    }
    .panel {
      border: 1px solid var(--line);
      background: rgba(17, 27, 38, .9);
      padding: 16px;
    }
    .tables {
      display: grid;
      gap: 12px;
    }
    .table {
      border: 1px solid var(--line);
      background: #101a25;
      padding: 14px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }
    h2, h3 { margin: 0; }
    h2 { color: var(--gold); font-size: 16px; }
    h3 { font-size: 17px; }
    p { margin: 6px 0 0; color: var(--muted); }
    a.button, button {
      min-height: 38px;
      border: 1px solid #35a673;
      background: var(--green);
      color: var(--text);
      padding: 9px 12px;
      font: inherit;
      font-weight: 700;
      text-decoration: none;
      text-align: center;
      cursor: pointer;
    }
    .secondary {
      background: #203246;
      border-color: #4b657e;
    }
    .message { color: var(--gold); }
    @media (max-width: 680px) {
      header { align-items: flex-start; flex-direction: column; }
      .table { grid-template-columns: 1fr; }
      .status { white-space: normal; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Discord Poker</h1>
      <div class="status" id="viewer">Connecting</div>
    </header>
    <section class="content">
      <div class="panel" id="authPanel"></div>
      <div class="panel">
        <h2>Live Tables</h2>
        <div class="tables" id="tables"></div>
      </div>
    </section>
  </main>
  <script>
    const viewer = document.getElementById('viewer');
    const authPanel = document.getElementById('authPanel');
    const tables = document.getElementById('tables');
    let latest = null;
    let activityAuthAttempted = false;
    let activityAuthRunning = false;
    let activityAuthFailed = false;

    function text(value) {
      return value === null || value === undefined || value === '' ? '-' : String(value);
    }

    function html(value) {
      return text(value).replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char]));
    }

    function render(data) {
      latest = data;
      viewer.textContent = data.authenticated ? data.viewer_name : 'Not signed in';
      renderAuthPanel(data);
      if (data.authenticated && data.launch_table_id) {
        window.location.href = `/table/${data.launch_table_id}`;
        return;
      }
      tables.innerHTML = data.tables.map(table => `
        <div class="table">
          <div>
            <h3>${table.mode.toUpperCase()} Table ${table.channel_id}</h3>
            <p>${table.players.length} players - ${table.phase} - blinds ${table.small_blind}/${table.big_blind}</p>
          </div>
          <a class="button" href="/table/${table.channel_id}">Open</a>
        </div>
      `).join('') || '<p>No live tables yet. Create one with /poker_online_create or /poker_offline_create.</p>';
      if (!data.authenticated && !activityAuthAttempted && data.activity_client_id) {
        startDiscordActivityAuth(data.activity_client_id);
      }
    }

    function renderAuthPanel(data) {
      if (data.authenticated) {
        authPanel.innerHTML = `<h2>Ready</h2><p>Signed in as <strong>${html(data.viewer_name)}</strong>. Open a table and join from there.</p>`;
        return;
      }
      const status = activityAuthRunning
        ? '<p class="message">Authorizing with Discord...</p>'
        : activityAuthFailed
          ? '<p class="message">Discord authorization did not start. Use the Open Poker App button in Discord, not the browser backup link.</p>'
          : '<p class="message">Authorizing with Discord automatically...</p>';
      authPanel.innerHTML = `
        <h2>Discord Sign In</h2>
        ${status}
        <button data-auth-action="retry" data-client-id="${html(data.activity_client_id || '')}">Retry Discord Authorization</button>
        <a class="button secondary" href="/login">Browser Backup</a>
      `;
    }

    async function refresh() {
      const response = await fetch('/api/lobby', { cache: 'no-store' });
      if (!response.ok) throw new Error(await response.text());
      render(await response.json());
    }

    async function startDiscordActivityAuth(clientId) {
      if (!clientId || activityAuthRunning) return;
      activityAuthAttempted = true;
      activityAuthRunning = true;
      activityAuthFailed = false;
      renderAuthPanel(latest || { authenticated: false, activity_client_id: clientId });
      try {
        const { DiscordSDK } = await import('/assets/discord-sdk.mjs');
        const discordSdk = new DiscordSDK(clientId);
        await withTimeout(discordSdk.ready(), 10000);
        const { code } = await discordSdk.commands.authorize({
          client_id: clientId,
          response_type: 'code',
          state: '',
          prompt: 'none',
          scope: ['identify'],
        });
        const tokenData = await exchangeDiscordCode(code);
        await discordSdk.commands.authenticate({ access_token: tokenData.access_token });
        activityAuthRunning = false;
        await refresh();
      } catch (error) {
        activityAuthRunning = false;
        activityAuthFailed = true;
        renderAuthPanel(latest || { authenticated: false, activity_client_id: clientId });
      }
    }

    function withTimeout(promise, ms) {
      return Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Discord Activity SDK is not available here')), ms)),
      ]);
    }

    async function exchangeDiscordCode(code) {
      let lastError = null;
      for (const url of ['/.proxy/api/token', '/api/token']) {
        try {
          const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
          });
          const data = await response.json();
          if (response.ok) return data;
          lastError = new Error(data.error || 'Discord token exchange failed');
        } catch (error) {
          lastError = error;
        }
      }
      throw lastError || new Error('Discord token exchange failed');
    }

    refresh().catch(error => {
      viewer.textContent = 'Disconnected';
      authPanel.innerHTML = `<p class="message">${html(error.message)}</p>`;
    });
    setInterval(() => refresh().catch(() => {}), 3000);
  </script>
</body>
</html>
"""


class PokerWebServer:
    def __init__(self, registry: TableRegistry, config: AppConfig) -> None:
        self.registry = registry
        self.config = config
        self.sessions: dict[str, UserSession] = {}
        self.oauth_states: dict[str, str] = {}
        self.launch_targets: dict[int, int] = {}
        self.discord_sdk_source: str | None = None
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_get("/healthz", self.healthz)
        app.router.add_get("/login", self.login)
        app.router.add_get("/oauth/callback", self.oauth_callback)
        app.router.add_get("/logout", self.logout)
        app.router.add_get("/assets/discord-sdk.mjs", self.discord_sdk_asset)
        app.router.add_get("/.proxy/assets/discord-sdk.mjs", self.discord_sdk_asset)
        app.router.add_get("/table/{table_id}", self.table_page)
        app.router.add_post("/api/token", self.activity_token)
        app.router.add_post("/.proxy/api/token", self.activity_token)
        app.router.add_get("/api/lobby", self.lobby_api)
        app.router.add_get("/api/tables", self.tables_api)
        app.router.add_get("/api/tables/{table_id}", self.table_api)
        app.router.add_get("/api/tables/{table_id}/image", self.table_image)
        app.router.add_post("/api/tables/{table_id}/me/join", self.join_table)
        app.router.add_post("/api/tables/{table_id}/me/leave", self.leave_table)
        app.router.add_post("/api/tables/{table_id}/action", self.table_action)
        app.router.add_post("/api/tables/{table_id}/me/action", self.player_action)
        app.router.add_post("/api/tables/{table_id}/seat/move", self.seat_move)
        app.router.add_post("/api/tables/{table_id}/offline/board", self.offline_board)
        app.router.add_post("/api/tables/{table_id}/offline/cards", self.offline_cards)
        app.router.add_post("/api/tables/{table_id}/award", self.award)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.config.web_host, self.config.web_port)
        await self.site.start()
        logger.info("Poker web server listening on %s:%s", self.config.web_host, self.config.web_port)

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def index(self, request: web.Request) -> web.Response:
        return web.Response(text=LOBBY_HTML, content_type="text/html")

    async def healthz(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "tables": len(self.registry.tables())})

    async def discord_sdk_asset(self, request: web.Request) -> web.Response:
        if self.discord_sdk_source is None:
            async with ClientSession() as session:
                async with session.get(DISCORD_SDK_URL) as response:
                    if response.status >= 400:
                        raise web.HTTPBadGateway(text="Discord Embedded App SDK could not be loaded.")
                    self.discord_sdk_source = await response.text()
        return web.Response(text=self.discord_sdk_source, content_type="text/javascript")

    async def table_page(self, request: web.Request) -> web.Response:
        return web.Response(text=HTML, content_type="text/html")

    async def lobby_api(self, request: web.Request) -> web.Response:
        user = self.current_user(request)
        user_id = int(user["user_id"]) if user else None
        launch_table_id = self.launch_targets.pop(user_id, None) if user_id is not None else None
        tables = self.registry.tables()
        if launch_table_id is not None and not any(table.channel_id == launch_table_id for table in tables):
            launch_table_id = None
        return web.json_response(
            {
                "authenticated": user is not None,
                "viewer_name": user["username"] if user else None,
                "activity_client_id": self.config.discord_client_id,
                "launch_table_id": launch_table_id,
                "tables": [table.snapshot() for table in tables],
            }
        )

    async def tables_api(self, request: web.Request) -> web.Response:
        return web.json_response([table.snapshot() for table in self.registry.tables()])

    async def table_api(self, request: web.Request) -> web.Response:
        try:
            user = self.current_user(request)
            viewer_id = int(user["user_id"]) if user else None
            data = serialize_viewer_table(self.registry, request.match_info["table_id"], viewer_id)
            data["authenticated"] = user is not None
            data["viewer_name"] = user["username"] if user else None
            data["activity_client_id"] = self.config.discord_client_id
            return web.json_response(data)
        except ValueError as exc:
            raise web.HTTPNotFound(text=str(exc))

    async def table_image(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.current_user(request)
            parsed_viewer = int(user["user_id"]) if user and int(user["user_id"]) in table.players else None
            return web.Response(body=render_table(table, parsed_viewer).getvalue(), content_type="image/png")
        except ValueError as exc:
            raise web.HTTPNotFound(text=str(exc))

    async def player_action(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            user_id = int(user["user_id"])
            self.require_seated(table, user_id)
            payload = await request.json()
            action = str(payload.get("action", ""))
            amount = payload.get("amount")
            message = table.apply_action(
                user_id,
                Action(action),
                int(amount) if amount not in (None, "") else None,
            )
            await self.registry.record_finished_hand_once(table)
            await self.registry.publish("web.player_action", table, user_id=user_id, action=action)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def join_table(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            user_id = int(user["user_id"])
            message = table.add_player(user_id, str(user["username"]))
            await self.registry.publish("web.player_joined", table, user_id=user_id)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def leave_table(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            user_id = int(user["user_id"])
            message = table.remove_player(user_id)
            await self.registry.publish("web.player_left", table, user_id=user_id)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def table_action(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            self.require_seated(table, int(user["user_id"]))
            payload = await request.json()
            action = payload.get("action")
            if action == "start":
                table.start_hand()
                message = "Hand started."
            elif action == "showdown":
                table.finish_showdown()
                message = "Showdown resolved."
            else:
                if table.mode != "offline":
                    raise ValueError("Player actions must use the logged-in player controls.")
                user_id = int(payload["user_id"])
                amount = payload.get("amount")
                message = table.apply_action(
                    user_id,
                    Action(action),
                    int(amount) if amount not in (None, "") else None,
                )
            await self.registry.record_finished_hand_once(table)
            await self.registry.publish("web.action", table, action=action)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def seat_move(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            user_id = int(user["user_id"])
            self.require_seated(table, user_id)
            payload = await request.json()
            message = table.move_player_to_seat(user_id, int(payload["seat"]))
            await self.registry.publish("web.seat_moved", table, user_id=user_id)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def offline_board(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            self.require_seated(table, int(user["user_id"]))
            payload = await request.json()
            message = table.set_offline_board(str(payload.get("cards", "")))
            await self.registry.publish("web.offline_board", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def offline_cards(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            self.require_seated(table, int(user["user_id"]))
            payload = await request.json()
            message = table.set_offline_cards(int(payload["user_id"]), str(payload.get("cards", "")))
            await self.registry.publish("web.offline_cards", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def award(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            user = self.require_user(request)
            self.require_seated(table, int(user["user_id"]))
            payload = await request.json()
            message = table.manual_award([int(payload["user_id"])])
            await self.registry.record_finished_hand_once(table)
            await self.registry.publish("web.award", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    def error_response(self, exc: Exception) -> web.Response:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    async def login(self, request: web.Request) -> web.Response:
        if not self.config.discord_client_id or not self.config.discord_client_secret:
            return self.error_response(ValueError("Discord login is not configured. Set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET."))
        state = secrets.token_urlsafe(24)
        self.oauth_states[state] = _safe_next_path(request.query.get("next"))
        params = {
            "client_id": self.config.discord_client_id,
            "redirect_uri": self.config.discord_redirect_uri,
            "response_type": "code",
            "scope": "identify",
            "state": state,
        }
        raise web.HTTPFound(f"https://discord.com/oauth2/authorize?{urlencode(params)}")

    async def oauth_callback(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state", "")
        next_path = self.oauth_states.pop(state, None)
        if not code or next_path is None:
            raise web.HTTPBadRequest(text="Missing Discord OAuth code or state.")

        token_payload = {
            "client_id": self.config.discord_client_id,
            "client_secret": self.config.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.discord_redirect_uri,
        }
        async with ClientSession() as session:
            async with session.post("https://discord.com/api/oauth2/token", data=token_payload) as token_response:
                if token_response.status >= 400:
                    raise web.HTTPUnauthorized(text="Discord token exchange failed.")
                token_data = await token_response.json()
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            async with session.get("https://discord.com/api/users/@me", headers=headers) as user_response:
                if user_response.status >= 400:
                    raise web.HTTPUnauthorized(text="Discord user lookup failed.")
                user_data = await user_response.json()

        session_id = self.create_session(user_data)
        response = web.HTTPFound(next_path)
        self.set_session_cookie(response, session_id)
        raise response

    async def activity_token(self, request: web.Request) -> web.Response:
        if not self.config.discord_client_id or not self.config.discord_client_secret:
            return self.error_response(ValueError("Discord Activity auth is not configured."))
        payload = await request.json()
        code = str(payload.get("code", ""))
        if not code:
            return self.error_response(ValueError("Discord authorization code is required."))

        token_payload = {
            "client_id": self.config.discord_client_id,
            "client_secret": self.config.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
        }
        async with ClientSession() as session:
            async with session.post("https://discord.com/api/oauth2/token", data=token_payload) as token_response:
                if token_response.status >= 400:
                    raise web.HTTPUnauthorized(text="Discord token exchange failed.")
                token_data = await token_response.json()
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            async with session.get("https://discord.com/api/users/@me", headers=headers) as user_response:
                if user_response.status >= 400:
                    raise web.HTTPUnauthorized(text="Discord user lookup failed.")
                user_data = await user_response.json()

        session_id = self.create_session(user_data)
        response = web.json_response(
            {
                "access_token": token_data["access_token"],
                "user": {
                    "id": user_data["id"],
                    "username": user_data.get("global_name") or user_data.get("username") or user_data["id"],
                },
            }
        )
        self.set_session_cookie(response, session_id)
        return response

    async def logout(self, request: web.Request) -> web.Response:
        session_id = request.cookies.get("poker_session", "")
        if session_id:
            self.sessions.pop(session_id, None)
        response = web.HTTPFound(_safe_next_path(request.query.get("next")))
        response.del_cookie("poker_session")
        raise response

    def current_user(self, request: web.Request) -> UserSession | None:
        session_id = request.cookies.get("poker_session", "")
        if session_id in self.sessions:
            return self.sessions[session_id]
        return self.decode_session(session_id)

    def require_user(self, request: web.Request) -> UserSession:
        user = self.current_user(request)
        if user is None:
            raise ValueError("Log in with Discord first.")
        return user

    def require_seated(self, table: PokerTable, user_id: int) -> None:
        if user_id not in table.players:
            raise ValueError("Join this table before playing.")

    def create_session(self, user_data: dict[str, object]) -> str:
        payload = {
            "user_id": int(user_data["id"]),
            "username": user_data.get("global_name") or user_data.get("username") or user_data["id"],
            "avatar": user_data.get("avatar"),
            "exp": int(time.time()) + 60 * 60 * 24 * 14,
        }
        session_id = self.encode_session(payload)
        self.sessions[session_id] = payload
        return session_id

    def encode_session(self, payload: UserSession) -> str:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
        signature = hmac.new(self.cookie_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
        signed = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        return f"v1.{encoded}.{signed}"

    def decode_session(self, value: str) -> UserSession | None:
        try:
            version, encoded, signed = value.split(".", 2)
            if version != "v1":
                return None
            expected = hmac.new(self.cookie_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
            actual = base64.urlsafe_b64decode(signed + "=" * (-len(signed) % 4))
            if not hmac.compare_digest(expected, actual):
                return None
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            payload = json.loads(raw.decode("utf-8"))
            if int(payload.get("exp", 0)) < time.time():
                return None
            return payload
        except Exception:
            return None

    def cookie_secret(self) -> bytes:
        secret = self.config.session_secret or self.config.discord_client_secret or self.config.discord_token
        return secret.encode("utf-8")

    def set_session_cookie(self, response: web.StreamResponse, session_id: str) -> None:
        is_https = self.config.public_base_url.startswith("https://")
        response.set_cookie(
            "poker_session",
            session_id,
            httponly=True,
            secure=is_https,
            samesite="None" if is_https else "Lax",
            max_age=60 * 60 * 24 * 14,
        )

    def set_launch_target(self, user_id: int, table_id: int) -> None:
        self.launch_targets[user_id] = table_id
