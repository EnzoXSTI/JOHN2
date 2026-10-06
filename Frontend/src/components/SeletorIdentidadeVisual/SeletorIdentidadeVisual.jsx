import { Palette } from 'lucide-react';
import MaskedInput from '../MaskedInput/MaskedInput';
import styles from './SeletorIdentidadeVisual.module.css';

const CAMPOS = [
    { chave: 'primaria', titulo: 'Cor primária', ajuda: 'Botões e destaques' },
    { chave: 'secundaria', titulo: 'Cor secundária', ajuda: 'Fundos escuros e contraste' },
    { chave: 'terciaria', titulo: 'Cor terciária', ajuda: 'Fundo principal' },
    { chave: 'textoPrimario', titulo: 'Texto principal', ajuda: 'Títulos sobre fundo claro' },
    { chave: 'textoSecundario', titulo: 'Texto secundário', ajuda: 'Textos sobre fundo escuro' },
];

/** Permite escolher visualmente ou informar o hexadecimal exato das cinco cores. */
export default function SeletorIdentidadeVisual({ value, onChange }) {
    function atualizar(chave, cor) {
        if (/^#[0-9A-Fa-f]{6}$/.test(cor)) onChange({ ...value, [chave]: cor.toUpperCase() });
    }

    return <div>
        <div className={styles.sectionHead}><span className={styles.dot}><Palette size={16} /></span>Identidade visual</div>
        <p className={styles.ajuda}>Escolha as cores de fundo, destaque e textos da sua barbearia.</p>
        <div className={styles.opcoes}>
            {CAMPOS.map((campo) => <label className={styles.opcao} key={campo.chave}>
                <span className={styles.label}>{campo.titulo}</span><span className={styles.descricao}>{campo.ajuda}</span>
                <span className={styles.controleCor}><input aria-label={campo.titulo} type="color" value={value[campo.chave]} onChange={(e) => atualizar(campo.chave, e.target.value)} /><MaskedInput className={styles.hex} mask={/^#[0-9A-Fa-f]{0,6}$/} value={value[campo.chave]} maxLength="7" onAccept={(cor) => atualizar(campo.chave, cor)} /></span>
            </label>)}
        </div>
    </div>;
}
