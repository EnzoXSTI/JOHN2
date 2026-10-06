import { IMaskInput } from 'react-imask';

/**
 * Componente base para os campos do Cortaê.
 *
 * Ele usa IMaskInput, mas recebe as mesmas propriedades visuais
 * que os inputs antigos. Assim, o CSS existente continua sendo
 * aplicado por meio de className.
 */
export default function MaskedInput({
    mask = /^[\s\S]*$/,
    onChange,
    onAccept,
    ...props
}) {
    return (
        <IMaskInput
            {...props}
            mask={mask}
            onAccept={(value, maskRef, event) => {
                // onAccept é o evento principal do IMask.
                // Também mantemos onChange para compatibilidade
                // com o comportamento esperado dos formulários React.
                if (onAccept) {
                    onAccept(value, maskRef, event);
                }

                if (onChange && event) {
                    onChange(event);
                }
            }}
        />
    );
}
