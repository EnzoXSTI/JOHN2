import { useEffect, useReducer } from "react";
import { X, Plus, Scissors, Pencil } from "lucide-react";
import styles from "./ModalAdicionarServico.module.css";

export default function ModalAdicionarServico({
    open,
    onClose,
    onAdd,
    servicoEditando = null
}) {
    const [formulario, atualizarFormulario] = useReducer(
        (estado, acao) => {
            if (acao.tipo === "substituir") return acao.valor;
            return { ...estado, [acao.campo]: acao.valor };
        },
        { nome: "", preco: "", duracao: "30", descricao: "", genero: "" }
    );
    const { nome, preco, duracao, descricao, genero } = formulario;

    const editando = servicoEditando !== null && servicoEditando !== undefined;

    useEffect(() => {
        if (!open) return;

        if (editando) {
            const nomeServico =
                servicoEditando.nome ??
                servicoEditando.nome_servico ??
                "";

            const precoServico =
                servicoEditando.preco ??
                servicoEditando.preco_servico ??
                "";

            const duracaoServico =
                servicoEditando.duracao ??
                servicoEditando.duracao_servico ??
                30;

            const descricaoServico =
                servicoEditando.descricao ??
                servicoEditando.descricao_breve ??
                servicoEditando.descricaoBreve ??
                "";

            atualizarFormulario({
                tipo: "substituir",
                valor: {
                    nome: String(nomeServico),
                    preco: precoServico === "" ? "" : String(precoServico).replace(".", ","),
                    duracao: String(Number.parseInt(duracaoServico, 10) || 30),
                    descricao: String(descricaoServico),
                    genero: String(servicoEditando.genero || "unissex")
                }
            });
        } else {
            atualizarFormulario({
                tipo: "substituir",
                valor: { nome: "", preco: "", duracao: "30", descricao: "", genero: "" }
            });
        }
    }, [open, servicoEditando, editando]);

    if (!open) return null;

    const valorNumerico = Number(
        String(preco).replace(/\./g, "").replace(",", ".")
    );

    const duracaoNumerica = Number.parseInt(duracao, 10);

    const podeSalvar =
        nome.trim().length > 0 &&
        ["masculino", "feminino", "unissex"].includes(genero) &&
        preco !== "" &&
        Number.isFinite(valorNumerico) &&
        valorNumerico >= 0 &&
        Number.isInteger(duracaoNumerica) &&
        duracaoNumerica > 0 &&
        duracaoNumerica <= 480;

    const handleSalvar = async () => {
        if (!podeSalvar) return;

        await onAdd({
            nome: nome.trim(),
            preco,
            duracao: duracaoNumerica,
            descricao: descricao.trim(),
            genero
        });
    };

    return (
        <div
            role="dialog"
            aria-modal="true"
            className={styles.overlay}
            onClick={onClose}
        >
            <form
                className={styles.modal}
                onClick={(e) => e.stopPropagation()}
                onSubmit={(e) => {
                    e.preventDefault();
                    handleSalvar();
                }}
            >
                <button
                    type="button"
                    className={styles.fechar}
                    onClick={onClose}
                    aria-label="Fechar"
                >
                    <X size={20} />
                </button>

                <h2 className={styles.titulo}>
                    {editando ? "Editar Serviço" : "Adicionar Serviço"}
                </h2>

                <div className={styles.regua} />

                <label className={styles.label} htmlFor="nome-servico">
                    Nome do Serviço
                </label>

                <input
                    id="nome-servico"
                    className={`${styles.input} ${styles.campoNome}`}
                    placeholder="Ex: Corte Degradê"
                    value={nome}
                    onChange={(e) => atualizarFormulario({ campo: "nome", valor: e.target.value })}
                />

                <label className={styles.label} htmlFor="genero-servico">
                    Público do serviço
                </label>
                <select
                    id="genero-servico"
                    className={`${styles.select} ${styles.campoGenero}`}
                    value={genero}
                    onChange={(e) => atualizarFormulario({ campo: "genero", valor: e.target.value })}
                    required
                >
                    <option value="" disabled>Selecione uma opção</option>
                    <option value="masculino">Masculino</option>
                    <option value="feminino">Feminino</option>
                    <option value="unissex">Unissex</option>
                </select>

                <div className={styles.linhaDupla}>
                    <div>
                        <label className={styles.label} htmlFor="preco-servico">
                            Preço (R$)
                        </label>

                        <input
                            id="preco-servico"
                            className={styles.input}
                            placeholder="00,00"
                            inputMode="decimal"
                            value={preco}
                            onChange={(e) =>
                                atualizarFormulario({ campo: "preco", valor: e.target.value.replace(/[^0-9,.]/g, "") })
                            }
                            required
                        />
                    </div>

                    <div>
                        <label className={styles.label} htmlFor="duracao-servico">
                            Duração do serviço (min)
                        </label>

                        <input
                            id="duracao-servico"
                            className={styles.input}
                            placeholder="Ex: 45"
                            inputMode="numeric"
                            type="number"
                            min={1}
                            max={480}
                            step={1}
                            list="duracoes-sugeridas"
                            value={duracao}
                            onChange={(e) =>
                                atualizarFormulario({ campo: "duracao", valor: e.target.value.replace(/[^0-9]/g, "") })
                            }
                            required
                        />
                        <small className={styles.ajudaDuracao}>
                            Digite os minutos. Ex.: 45
                        </small>
                        <datalist id="duracoes-sugeridas">
                            <option value="15" />
                            <option value="30" />
                            <option value="45" />
                            <option value="60" />
                            <option value="90" />
                            <option value="120" />
                        </datalist>
                    </div>
                </div>

                <label className={styles.label} htmlFor="descricao-servico">
                    Descrição Breve
                </label>

                <textarea
                    id="descricao-servico"
                    className={styles.textarea}
                    placeholder="Descreva os detalhes do serviço..."
                    value={descricao}
                    onChange={(e) => atualizarFormulario({ campo: "descricao", valor: e.target.value })}
                    style={{ marginBottom: 14 }}
                />

                <div className={styles.dica}>
                    <Scissors size={16} color="var(--cor-destaque)" />
                    Personalize os detalhes para seus clientes.
                </div>

                <button
                    type="submit"
                    className={styles.botaoPrimario}
                    disabled={!podeSalvar}
                >
                    {editando ? <Pencil size={16} /> : <Plus size={16} />}
                    {editando ? "SALVAR ALTERAÇÕES" : "ADICIONAR"}
                </button>

                <button
                    type="button"
                    className={styles.botaoCancelar}
                    onClick={onClose}
                >
                    CANCELAR
                </button>
            </form>
        </div>
    );
}
