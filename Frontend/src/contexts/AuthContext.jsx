import { useCallback, useEffect, useState } from 'react';
import { lerUsuarioLocal } from './authStorage';
import { AuthContext } from './contextoAutenticacao';

// ==========================================================
// CONTEXTO DE AUTENTICAÇÃO
// ==========================================================
// Centraliza o estado do usuário logado. A API autentica via
// cookie HttpOnly (credentials: 'include' em services/api.js);
// o espelho em localStorage ('usuario') serve só para o front
// saber quem está logado sem uma requisição extra.

export function AuthProvider({ children }) {
    const [usuario, setUsuario] = useState(() => lerUsuarioLocal());

    const recarregar = useCallback(() => {
        setUsuario(lerUsuarioLocal());
    }, []);

    useEffect(() => {
        window.addEventListener('loginAlterado', recarregar);
        window.addEventListener('storage', recarregar);
        return () => {
            window.removeEventListener('loginAlterado', recarregar);
            window.removeEventListener('storage', recarregar);
        };
    }, [recarregar]);

    return (
        <AuthContext.Provider value={{ usuario, logado: !!usuario, recarregar }}>
            {children}
        </AuthContext.Provider>
    );
}
