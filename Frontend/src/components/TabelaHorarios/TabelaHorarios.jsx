import { Clock } from "lucide-react";
import styles from "./TabelaHorarios.module.css";

/**
 * Tabela de horários de funcionamento por dia da semana.
 *
 * @param {Array<{nome: string, fechado: boolean, manhaInicio: string, manhaFim: string, tardeInicio: string, tardeFim: string}>} dias
 * @param {(nomeDia: string) => void} onToggleDia - alterna aberto/fechado ao clicar no nome do dia
 * @param {(nomeDia: string, campo: string, valor: string) => void} onChangeHorario
 */
export default function TabelaHorarios({ dias, onToggleDia, onChangeHorario }) {
    return (
        <div>
            <div className={styles.sectionHead}>
        <span className={styles.dot}>
          <Clock size={16} />
        </span>
                Horário de serviço por dia de serviço
            </div>

            <div className={styles.scrollWrap}>
                <div className={styles.tabela}>
                    <div className={styles.cabecalho}>
                        <span>Dia</span>
                        <span>Manhã (início – fim)</span>
                        <span>Tarde (início – fim)</span>
                    </div>

                    {dias.map((dia) => (
                        <div key={dia.nome} className={styles.linha}>
                            <button
                                type="button"
                                className={styles.diaBotao}
                                onClick={() => onToggleDia(dia.nome)}
                                title="Alternar fechado/aberto"
                            >
                                {dia.nome}
                            </button>

                            {dia.fechado ? (
                                <span className={styles.fechado}>Estabelecimento Fechado</span>
                            ) : (
                                <>
                                    <div className={styles.periodo}>
                                        <input
                                            className={styles.inputHora}
                                            type="time"
                                            value={dia.manhaInicio}
                                            onChange={(e) => onChangeHorario(dia.nome, "manhaInicio", e.target.value)}
                                        />
                                        <input
                                            className={styles.inputHora}
                                            type="time"
                                            value={dia.manhaFim}
                                            onChange={(e) => onChangeHorario(dia.nome, "manhaFim", e.target.value)}
                                        />
                                    </div>
                                    <div className={styles.periodo}>
                                        <input
                                            className={styles.inputHora}
                                            type="time"
                                            value={dia.tardeInicio}
                                            onChange={(e) => onChangeHorario(dia.nome, "tardeInicio", e.target.value)}
                                        />
                                        <input
                                            className={styles.inputHora}
                                            type="time"
                                            value={dia.tardeFim}
                                            onChange={(e) => onChangeHorario(dia.nome, "tardeFim", e.target.value)}
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
