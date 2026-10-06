export function lerUsuarioLocal() {
    try {
        const bruto = localStorage.getItem('usuario');
        if (!bruto) return null;

        const dados = JSON.parse(bruto);
        return dados && dados.id_usuario ? dados : null;
    } catch {
        return null;
    }
}
