import { FiScissors } from 'react-icons/fi';
import styles from './CardServico.module.css';

export default function CardServico({ nome, tempo, preco, selecionado, onClick }) {
    const conteudo = <>
        <div className={styles.icone}>
            <FiScissors />
        </div>
        <div className={styles.informacoes}>
            <h3>{nome}</h3>
            <span>{tempo}</span>
        </div>
        <strong>{preco}</strong>
    </>;

    if (!onClick) {
        return <div className={styles.card}>{conteudo}</div>;
    }

    return (
        <button
            type="button"
            className={`${styles.card} ${selecionado ? styles.selecionado : ''}`}
            onClick={onClick}
            aria-pressed={selecionado}
        >
            {conteudo}
        </button>
    );
}
