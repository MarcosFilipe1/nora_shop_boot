const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

const ROOT     = path.join(__dirname, '..');
const AUTH_DIR = path.join(__dirname, 'auth');
const QUEUE_F  = path.join(ROOT, 'data', 'wa_queue.json');
const STATUS_F = path.join(ROOT, 'data', 'wa_status.json');
const GROUPS_F = path.join(ROOT, 'data', 'wa_groups.json');
const LOG_F    = path.join(ROOT, 'logs', 'bot.log');

function ensureDirs() {
    [path.join(ROOT,'data'), path.join(ROOT,'logs'), AUTH_DIR].forEach(d => {
        if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
    });
}

function writeStatus(data) {
    fs.writeFileSync(STATUS_F, JSON.stringify({ ...data, updated_at: new Date().toISOString() }, null, 2));
}

function log(nivel, msg) {
    const ts = new Date().toISOString().replace('T',' ').slice(0,19);
    const line = `${ts} [${nivel}] ${msg}\n`;
    process.stdout.write(line);
    fs.appendFileSync(LOG_F, line);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function randDelay(min=8, max=20) { return sleep((min + Math.random()*(max-min))*1000); }

ensureDirs();
writeStatus({ online: false, numero: null });

async function startBot() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false,
        logger: pino({ level: 'silent' }),
        browser: ['Nora Shop', 'Chrome', '120.0.0'],
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.clear();
            console.log('\n🛍️  Nora Shop — Conectar WhatsApp\n');
            qrcode.generate(qr, { small: true });
            console.log('\nEscaneie com o WhatsApp...\n');
            writeStatus({ online: false, qr_pendente: true });
        }

        if (connection === 'open') {
            const numero = sock.user.id.split(':')[0];
            log('SUCCESS', `WhatsApp conectado — ${numero}`);
            writeStatus({ online: true, numero });

            // Lista grupos
            await listarGrupos(sock);

            // Inicia fila
            processarFila(sock);
        }

        if (connection === 'close') {
            const reason = lastDisconnect?.error?.output?.statusCode;
            log('WARNING', `Desconectado: ${reason}`);
            writeStatus({ online: false, numero: null });

            if (reason !== DisconnectReason.loggedOut) {
                log('INFO', 'Reconectando em 5s...');
                await sleep(5000);
                startBot();
            } else {
                log('ERROR', 'Logout detectado. Remova a pasta auth/ e reconecte.');
            }
        }
    });

    return sock;
}

async function listarGrupos(sock) {
    try {
        const groups = await sock.groupFetchAllParticipating();
        const lista = Object.values(groups).map(g => ({
            id: g.id,
            name: g.subject,
            participants: g.participants?.length || 0,
        }));
        fs.writeFileSync(GROUPS_F, JSON.stringify(lista, null, 2));
        log('INFO', `${lista.length} grupos encontrados`);
        lista.forEach(g => log('INFO', `  ${g.name} (${g.participants} membros) — ${g.id}`));
        return lista;
    } catch(e) {
        log('ERROR', `Erro ao listar grupos: ${e.message}`);
        return [];
    }
}

async function enviarTexto(sock, destino, texto) {
    try {
        await sock.sendMessage(destino, { text: texto });
        log('SUCCESS', `Enviado para ${destino}`);
        return true;
    } catch(e) {
        log('ERROR', `Falha ${destino}: ${e.message}`);
        return false;
    }
}

async function enviarImagem(sock, destino, imagemUrl, legenda) {
    try {
        await sock.sendMessage(destino, {
            image: { url: imagemUrl },
            caption: legenda,
        });
        log('SUCCESS', `Imagem enviada para ${destino}`);
        return true;
    } catch(e) {
        log('ERROR', `Falha imagem ${destino}: ${e.message}`);
        return false;
    }
}

async function processarFila(sock) {
    log('INFO', 'Monitorando fila de envios...');

    setInterval(async () => {
        if (!fs.existsSync(QUEUE_F)) return;
        let fila = [];
        try { fila = JSON.parse(fs.readFileSync(QUEUE_F, 'utf8')); } catch { return; }
        if (!fila.length) return;

        const item = fila.shift();
        fs.writeFileSync(QUEUE_F, JSON.stringify(fila, null, 2));

        log('INFO', `Processando: ${item.id}`);

        const destinos = item.grupos || [];
        for (const gid of destinos) {
            if (item.imagem) {
                const ok = await enviarImagem(sock, gid, item.imagem, item.texto);
                if (!ok) await enviarTexto(sock, gid, item.texto);
            } else {
                await enviarTexto(sock, gid, item.texto);
            }
            await randDelay(8, 20);
        }
    }, 10000);
}

// Comando via stdin
process.stdin.setEncoding('utf8');
process.stdin.on('data', async (data) => {
    const cmd = data.trim();
    if (cmd === 'grupos') {
        log('INFO', 'Atualizando lista de grupos...');
    }
});

log('INFO', 'Iniciando Baileys...');
startBot();
