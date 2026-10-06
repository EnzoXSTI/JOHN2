import { useEffect, useState } from 'react';
import styles from './CarrosselImagens.module.css';

export default function CarrosselImagens({ imagens }) {
    const [imagemAtual, setImagemAtual] = useState(0);
    const [animando, setAnimando] = useState(false);

    useEffect(() => {
        const intervalo = setInterval(() => {
            setAnimando(true);

            setTimeout(() => {
                setImagemAtual((atual) =>
                    atual === imagens.length - 1 ? 0 : atual + 1
                );

                setAnimando(false);
            }, 500);
        }, 3500);

        return () => clearInterval(intervalo);
    }, [imagens.length]);

    const selecionarImagem = (index) => {
        if (index === imagemAtual) return;

        setAnimando(true);

        setTimeout(() => {
            setImagemAtual(index);
            setAnimando(false);
        }, 500);
    };

    return (
        <div className={styles.carrossel}>
            <div className={styles.imagemWrapper}>
                {imagens.map((imagem, index) => (
                    <img
                        key={imagem}
                        src={imagem}
                        alt={`Interior da barbearia - imagem ${index + 1}`}
                        className={`${styles.imagem} ${
    index === imagemAtual ? styles.ativa : ''
} ${
    index === imagemAtual && animando
        ? styles.saindo
        : ''
}`}
                    />
                ))}

                <div className={styles.overlay}></div>

                <div className={styles.indicadores}>
                    {imagens.map((_, index) => (
                        <button
                            key={index}
                            className={
                                index === imagemAtual
                                    ? styles.indicadorAtivo
                                    : styles.indicador
                            }
                            onClick={() => selecionarImagem(index)}
                            aria-label={`Ir para imagem ${index + 1}`}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}

