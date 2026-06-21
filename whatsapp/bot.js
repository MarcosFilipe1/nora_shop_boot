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

// ── CONFIGURAÇÃO DE HORÁRIOS ──
const CONFIG = {
    horarioInicio: 8,
    horarioFim: 2,
    intervaloMinutos: 10,
    limites: {
        manha:  { inicio: 8,  fim: 12, max: 10 },
        tarde:  { inicio: 12, fim: 18, max: 5 },
        noite:  { inicio: 18, fim: 2, max: 15 },
    }
};

// Contadores de envio por período
let enviosPorPeriodo = { manha: 0, tarde: 0, noite: 0 };
let ultimoReset = new Date().toDateString();
let ultimoEnvio = {};

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

function getHoraBrasilia() {
    const now = new Date();
    const br = new Date(now.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' }));
    return br.getHours();
}

function getPeriodoAtual() {
    const hora = getHoraBrasilia();
    function dentro(p) {
        if (p.fim > p.inicio) return hora >= p.inicio && hora < p.fim;
        return hora >= p.inicio || hora < p.fim;
    }
    if (dentro(CONFIG.limites.manha)) return 'manha';
    if (dentro(CONFIG.limites.tarde)) return 'tarde';
    if (dentro(CONFIG.limites.noite)) return 'noite';
    return null;
}

function dentroDoHorario() {
    const hora = getHoraBrasilia();
    // Suporta horarios que cruzam meia-noite (ex: 8h-2h)
    if (CONFIG.horarioFim > CONFIG.horarioInicio) {
        return hora >= CONFIG.horarioInicio && hora < CONFIG.horarioFim;
    } else {
        return hora >= CONFIG.horarioInicio || hora < CONFIG.horarioFim;
    }
}

function resetarContadores() {
    const hoje = new Date().toDateString();
    if (hoje !== ultimoReset) {
        enviosPorPeriodo = { manha: 0, tarde: 0, noite: 0 };
        ultimoReset = hoje;
        log('INFO', 'Contadores de envio resetados para novo dia');
    }
}

function podeSendar(grupoId) {
    resetarContadores();

    if (!dentroDoHorario()) {
        log('INFO', `Fora do horario (${getHoraBrasilia()}h) — aguardando 8h-22h`);
        return false;
    }

    const periodo = getPeriodoAtual();
    if (!periodo) return false;

    const limite = CONFIG.limites[periodo].max;
    if (enviosPorPeriodo[periodo] >= limite) {
        log('INFO', `Limite ${periodo} atingido: ${enviosPorPeriodo[periodo]}/${limite}`);
        return false;
    }

    const agora = Date.now();
    const ultimo = ultimoEnvio[grupoId] || 0;
    const diff = (agora - ultimo) / 1000 / 60;
    if (diff < CONFIG.intervaloMinutos) {
        log('INFO', `Aguardando intervalo grupo ${grupoId}: ${CONFIG.intervaloMinutos - Math.floor(diff)}min restantes`);
        return false;
    }

    return true;
}

function registrarEnvio(grupoId) {
    const periodo = getPeriodoAtual();
    if (periodo) enviosPorPeriodo[periodo]++;
    ultimoEnvio[grupoId] = Date.now();
    log('INFO', `Envios ${periodo}: ${enviosPorPeriodo[periodo]}/${CONFIG.limites[periodo]?.max || '?'}`);
}

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
            await listarGrupos(sock);
            processarFila(sock);
        }

        if (connection === 'close') {
            const reason = lastDisconnect?.error?.output?.statusCode;
            log('WARNING', `Desconectado: ${reason}`);
            writeStatus({ online: false, numero: null });

            if (reason !== DisconnectReason.loggedOut) {
                log('INFO', 'Reconectando em 10s...');
                await sleep(10000);
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
    log('INFO', `Horario: ${CONFIG.horarioInicio}h-${CONFIG.horarioFim}h | Intervalo: ${CONFIG.intervaloMinutos}min`);
    log('INFO', `Limites — Manha: ${CONFIG.limites.manha.max} | Tarde: ${CONFIG.limites.tarde.max} | Noite: ${CONFIG.limites.noite.max}`);

    setInterval(async () => {
        if (!fs.existsSync(QUEUE_F)) return;
        let fila = [];
        try { fila = JSON.parse(fs.readFileSync(QUEUE_F, 'utf8')); } catch { return; }
        if (!fila.length) return;

        const item = fila[0];
        const destinos = item.grupos || [];

        // Verifica se pode enviar para pelo menos um grupo
        let enviouAlgum = false;
        const gruposRestantes = [];

        for (const gid of destinos) {
            if (!podeSendar(gid)) {
                gruposRestantes.push(gid);
                continue;
            }

            let ok = false;
            if (item.imagem) {
                ok = await enviarImagem(sock, gid, item.imagem, item.texto);
                if (!ok) ok = await enviarTexto(sock, gid, item.texto);
            } else {
                ok = await enviarTexto(sock, gid, item.texto);
            }

            if (ok) {
                registrarEnvio(gid);
                enviouAlgum = true;
            } else {
                gruposRestantes.push(gid);
            }

            await sleep(8000);
        }

        if (gruposRestantes.length === 0) {
            // Todos os grupos receberam — remove da fila
            fila.shift();
        } else {
            // Atualiza com grupos que faltam
            fila[0].grupos = gruposRestantes;
        }

        fs.writeFileSync(QUEUE_F, JSON.stringify(fila, null, 2));

    }, 30000); // Verifica a fila a cada 30 segundos
}

log('INFO', 'Iniciando Baileys...');
startBot();
