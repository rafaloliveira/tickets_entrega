import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3"
import nodemailer from "npm:nodemailer"

// Conexão com o Banco de Dados
const supabaseUrl = "https://vismjxhlsctehpvgmata.supabase.co";
// ATENÇÃO: Cole a sua SERVICE_ROLE_KEY aqui
const supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpc21qeGhsc2N0ZWhwdmdtYXRhIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NjU3MDg1MiwiZXhwIjoyMDYyMTQ2ODUyfQ.dIcTMaFGpSJu1M7AWW-OCyVCrBOq-FbRqiD2iLeMKE8"; 
const supabase = createClient(supabaseUrl, supabaseKey);

// Configuração do SMTP Gmail
const transporter = nodemailer.createTransport({
    host: "smtp.gmail.com",
    port: 587,
    secure: false,
    auth: {
        user: "ticketclicklogtransportes@gmail.com",
        pass: "gpbh tjyq wyvi jibs"
    }
});

serve(async (req: Request) => {
    try {
        console.log("🤖 Iniciando varredura de tickets...");
        
        const { data: clientes } = await supabase.from('clientes').select('*');
        if (!clientes) return new Response("Sem clientes", { status: 200 });

        const regras: Record<string, any> = {};
        clientes.forEach((c: any) => { 
            if (c.enviar_para_email) regras[c.cliente] = c; 
        });

        const { data: tickets } = await supabase.from('ocorrencias').select('*').eq('status', 'Aberta');
        if (!tickets || tickets.length === 0) {
            console.log("Nenhum ticket aberto.");
            return new Response("Nenhum ticket aberto.", { status: 200 });
        }

        const agora = new Date();
        const utc = agora.getTime() + (agora.getTimezoneOffset() * 60000);
        const agoraBrasil = new Date(utc - (3600000 * 3));

        for (const ocorr of tickets) {
            const regra = regras[ocorr.cliente];
            if (!regra) continue;
            if (!ocorr.data_abertura_manual || !ocorr.hora_abertura_manual) continue;

            const [ano, mes, dia] = ocorr.data_abertura_manual.split('-');
            const [hora, min, seg] = ocorr.hora_abertura_manual.split(':');
            const dtAbertura = new Date(Number(ano), Number(mes) - 1, Number(dia), Number(hora), Number(min), Number(seg || 0));

            const diffMs = agoraBrasil.getTime() - dtAbertura.getTime();
            const minDecorridos = Math.floor(diffMs / 60000);
            const ticketFormatado = String(ocorr.numero_ticket || '-').slice(-5);

            const janelas = [regra.janela_1, regra.janela_2, regra.janela_3, regra.janela_4, regra.janela_5];

            // 🟢 NOVA LÓGICA: Verifica do MAIOR tempo para o MENOR
            let alertaParaEnviar = -1;
            let janelaParaEnviar = 0;

            for (let i = 4; i >= 0; i--) {
                const janelaMinutos = janelas[i];
                const numAlerta = i + 1;
                const colunaFlag = `alerta_${numAlerta}_enviado`;

                if (janelaMinutos && minDecorridos >= janelaMinutos) {
                    if (ocorr[colunaFlag]) {
                        // Se o maior alerta que estourou o tempo já foi enviado, para a verificação e não manda nada
                        break;
                    } else {
                        // Achou o maior alerta que estourou o tempo e AINDA NÃO FOI enviado
                        alertaParaEnviar = numAlerta;
                        janelaParaEnviar = janelaMinutos;
                        break;
                    }
                }
            }

            if (alertaParaEnviar !== -1) {
                console.log(`📧 Disparando Alerta ${alertaParaEnviar} (${janelaParaEnviar}m) para o ticket ${ticketFormatado}`);
                
                const assunto = `Alerta de Permanência (${janelaParaEnviar} min) - Ticket ${ticketFormatado}`;
                
                const dataAberturaEmail = `${dia}/${mes}/${ano} ${hora}:${min}`;
                const imagemHtml = ocorr.imagem_url 
                    ? `<a href="${ocorr.imagem_url}" target="_blank" style="color:#007bff; text-decoration:none;">Visualizar Anexo</a>` 
                    : 'Não anexada';

                const corpo = `
                    <html>
                    <head><style>body {font-family: Arial; font-size: 14px;} table {border-collapse: collapse; width: 100%; max-width: 600px;} th, td {border: 1px solid #ddd; padding: 5px 8px; text-align: left;} th {background-color: #f2f2f2; width: 35%;}</style></head>
                    <body>
                        <div style="background-color: #d9534f; color: white; padding: 10px; max-width: 580px; border-radius: 4px 4px 0 0;"><h2>Notificação de Ocorrência em Aberto</h2></div>
                        <p>Prezado(a) cliente <strong>${ocorr.cliente}</strong>,</p>
                        <p>O veículo encontra-se no ponto de descarga há mais de <strong>${janelaParaEnviar} minutos</strong>.</p>
                        <p>Solicitamos sua atuação imediata para regularização do processo de descarga para evitar custos adicionais de TDE.</p>
                        <table>
                            <tr><th>Ticket</th><td>${ticketFormatado}</td></tr>
                            <tr><th>Nota Fiscal</th><td>${ocorr.nota_fiscal || '-'}</td></tr>
                            <tr><th>Destinatário</th><td>${ocorr.destinatario || '-'}</td></tr>
                            <tr><th>Cidade</th><td>${ocorr.cidade || '-'}</td></tr>
                            <tr><th>Tipo de Ocorrência</th><td>${ocorr.tipo_de_ocorrencia || '-'}</td></tr>
                            <tr><th>Data/Hora de Abertura</th><td>${dataAberturaEmail}</td></tr>
                            <tr><th>Imagem</th><td>${imagemHtml}</td></tr>
                        </table>
                        <p style="font-size: 11px; color: gray; margin-top: 20px;">⚠️ Este é um e-mail automático. Por favor, não responda.</p>
                        
                        <p style="margin-bottom: 5px;">Atenciosamente,<br>Equipe de Monitoramento ClikLog Transportes</p>
                        
                        <img src="https://vismjxhlsctehpvgmata.supabase.co/storage/v1/object/public/assets/logo.png" alt="Logo ClickLog" style="width: 150px; height: auto; margin-top: 10px;">
                    
                    </body>
                    </html>
                `;

                const copias = regra.email_copia ? regra.email_copia.replace(/;/g, ',') : '';
                const principal = regra.enviar_para_email.replace(/;/g, ',');

                await transporter.sendMail({
                    from: '"ClickLog Transportes" <ticketclicklogtransportes@gmail.com>',
                    to: principal,
                    cc: copias,
                    subject: assunto,
                    html: corpo,
                    replyTo: "noreply@clicklogtransportes.com.br"
                });

                // 🟢 Atualiza a Flag do alerta atual E DE TODOS OS ANTERIORES para TRUE no banco de dados
                const upData: Record<string, boolean> = {};
                for (let j = 1; j <= alertaParaEnviar; j++) {
                    upData[`alerta_${j}_enviado`] = true;
                }
                await supabase.from('ocorrencias').update(upData).eq('id', ocorr.id);

                await supabase.from('emails_enviados').insert({
                    data_hora: agoraBrasil.toISOString(),
                    tipo: `Alerta ${alertaParaEnviar} (${janelaParaEnviar}m)`,
                    cliente: ocorr.cliente,
                    email: principal,
                    ticket: ticketFormatado,
                    nota_fiscal: ocorr.nota_fiscal || '-',
                    status: 'Enviado',
                    provedor: 'Gmail SMTP (Edge)'
                });
            }
        }
        return new Response("Varredura concluída com sucesso!", { status: 200 });
    } catch (error) {
        console.error("❌ Erro fatal no motor:", error);
        return new Response(String(error), { status: 500 });
    }
})