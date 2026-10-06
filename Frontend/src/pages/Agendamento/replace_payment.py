# Script to replace payment functions in Agendamento.jsx
with open(r'C:\Users\mathe\Documents\Matheus G\Atividade Senai\Tem-que-testar-main\Tem-que-testar-main\Frontend\src\pages\Agendamento\Agendamento.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_functions = '''    }, [pagamento]);

    const copiarCodigo = async () => {
        if (!pagamento?.codigo_pagamento) return;
        try {
            await navigator.clipboard.writeText(pagamento.codigo_pagamento);
            setCopiado(true);
            window.setTimeout(() => setCopiado(false), 2000);
        } catch { setErro('Não foi possível copiar. Selecione o código manualmente.'); }
    };

    if (!idBarbearia || !idsServicos) {'''

new_functions = '''    }, [pagamento]);

    const copiarCodigo = async () => {
        if (!pagamento?.codigo_pagamento) return;
        try {
            await navigator.clipboard.writeText(pagamento.codigo_pagamento);
            setCopiado(true);
            window.setTimeout(() => setCopiado(false), 2000);
        } catch { setErro('Não foi possível copiar. Selecione o código manualmente.'); }
    };

    const selecionarMetodoPagamento = (metodo) => {
        setMetodoPagamento(metodo);
        if (metodo === 'pix') {
            gerarPix();
        } else if (metodo === 'boleto') {
            gerarBoleto();
        } else if (metodo === 'cartao') {
            processarCartao();
        } else if (metodo === 'na_hora') {
            confirmarPagamentoNaHora();
        }
    };

    const gerarPix = async () => {
        if (!idAgendamento) return;
        setCarregando(true); setErro('');
        try {
            const dados = await apiFetch('/pagamentos/pix', {
                method: 'POST', body: JSON.stringify({ id_agendamento: idAgendamento })
            });
            setPagamento({ ...dados, metodo: 'pix' });
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    const gerarBoleto = async () => {
        if (!idAgendamento) return;
        setCarregando(true); setErro('');
        try {
            const dados = await apiFetch('/pagamentos/boleto', {
                method: 'POST', body: JSON.stringify({ id_agendamento: idAgendamento })
            });
            setPagamento({ ...dados, metodo: 'boleto' });
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    const processarCartao = async () => {
        if (!idAgendamento) return;
        setCarregando(true); setErro('');
        try {
            const dados = await apiFetch('/pagamentos/cartao', {
                method: 'POST', body: JSON.stringify({ id_agendamento: idAgendamento })
            });
            setPagamento({ ...dados, metodo: 'cartao' });
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    const confirmarPagamentoNaHora = async () => {
        if (!idAgendamento) return;
        setCarregando(true); setErro('');
        try {
            const dados = await apiFetch('/pagamentos/na-hora', {
                method: 'POST', body: JSON.stringify({ id_agendamento: idAgendamento })
            });
            setPagamento({ ...dados, metodo: 'na_hora', status: 1 });
            setSucesso('Pagamento na hora confirmado! Redirecionando…');
            window.setTimeout(() => navigate(`/estabelecimento?usuario=${encodeURIComponent(idBarbearia)}`), 2000);
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    const voltarSelecaoPagamento = () => {
        setMetodoPagamento(null);
        setPagamento(null);
        setMostrarPagamento(true);
    };

    if (!idBarbearia || !idsServicos) {'''

content = content.replace(old_functions, new_functions)

with open(r'C:\Users\mathe\Documents\Matheus G\Atividade Senai\Tem-que-testar-main\Tem-que-testar-main\Frontend\src\pages\Agendamento\Agendamento.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')