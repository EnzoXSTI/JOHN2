import styles from "./footer.module.css";

import {
    FaFacebook,
    FaInstagram,
    FaYoutube
} from "react-icons/fa";
import {FaXTwitter} from "react-icons/fa6";

export default function Footer() {
    return (
        <footer className={styles.footer}>
            <div className={styles.container}>

                <div className={styles.logoArea}>
                    <img src={"/logobranca.png"} alt="CORTAÊ" />

                    <p>
                        Leve sua barbearia para o <br />
                        <strong>Próximo estágio.</strong>
                    </p>
                </div>

                <div className={styles.links}>
                    <h3>Acesso rápido</h3>

                    <a href="/">Início</a>
                    <a href="/">Encontrar estabelecimento</a>
                    <a href="/">Meus agendamentos</a>
                </div>

                <div className={styles.links}>
                    <h3>Mais</h3>

                    <a href="/">Sobre nós</a>
                    <a href="/">Trabalhe conosco</a>
                </div>

                <div className={styles.redes}>
                    <a href="#">
                        <FaFacebook />
                    </a>

                    <a href="#">
                        <FaInstagram />
                    </a>

                    <a href="#">
                        <FaYoutube />
                    </a>

                    <a href="#">
                        <FaXTwitter />
                    </a>
                </div>

            </div>

            <div className={styles.copy}>
                © 2026 CORTAÊ. Todos os direitos reservados.
            </div>
        </footer>
    );
}