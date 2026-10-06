import { createContext } from 'react';

export const AuthContext = createContext({
    usuario: null,
    logado: false,
    recarregar: () => {},
});
