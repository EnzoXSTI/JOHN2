import { useNavigate } from "react-router-dom";
import css from "./Button.module.css";

export default function Botao({ acao, pagina, texto, id }) {
    const navigate = useNavigate();

    function handleClick(e) {
        e.preventDefault();

        if (acao) {
            acao();
        }

        if (pagina) {
            navigate(pagina);
        }
    }

    return (
        <button
            id={id}
            type="button"
            className={css.botao}
            onClick={handleClick}
        >
            {texto}
        </button>
    );
}
