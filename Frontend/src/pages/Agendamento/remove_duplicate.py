# Remove duplicate gerarPix function
with open(r'C:\Users\mathe\Documents\Matheus G\Atividade Senai\Tem-que-testar-main\Tem-que-testar-main\Frontend\src\pages\Agendamento\Agendamento.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and remove the first gerarPix (lines 121-131)
old_code = '''    const gerarPix = async () => {
        if (!idAgendamento) return;
        setCarregando(true); setErro('');
        try {
            const dados = await apiFetch('/pagamentos/pix', {
                method: 'POST', body: JSON.stringify({ id_agendamento: idAgendamento })
            });
            setPagamento(dados);
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    const verificarPagamento = async () => {'''

new_code = '''    const verificarPagamento = async () => {'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(r'C:\Users\mathe\Documents\Matheus G\Atividade Senai\Tem-que-testar-main\Tem-que-testar-main\Frontend\src\pages\Agendamento\Agendamento.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Removed duplicate gerarPix!')
else:
    print('Pattern not found')