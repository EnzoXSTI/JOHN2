import { FiCheckCircle, FiAlertCircle, FiX } from 'react-icons/fi';
import styles from './MensagemCard.module.css';

export default function MensagemCard({
                                         mensagem,
                                         fechar
                                     }) {

    if (!mensagem) {
        return null;
    }

    const tipo =
        mensagem?.tipo === 'sucesso'
            ? 'sucesso'
            : 'erro';

    return (
        <div className={styles.overlay}>

            <div
                className={`${styles.card} ${
                    tipo === 'sucesso'
                        ? styles.cardSucesso
                        : styles.cardErro
                }`}
            >

                <button
                    type="button"
                    className={styles.fechar}
                    onClick={fechar}
                    aria-label="Fechar mensagem"
                >
                    <FiX />
                </button>


                <div className={styles.icone}>

                    {tipo === 'sucesso' ? (
                        <FiCheckCircle />
                    ) : (
                        <FiAlertCircle />
                    )}

                </div>


                <h2>
                    {tipo === 'sucesso'
                        ? 'Sucesso!'
                        : 'Atenção!'
                    }
                </h2>


                <p id = "mensagem">
                    {mensagem.informacao}
                </p>


                <button
                    type="button"
                    id='button-confirmar'
                    className={styles.botao}
                    onClick={fechar}
                >
                    OK
                </button>

            </div>

        </div>
    );
}