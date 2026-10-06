import firebirdsql

con = firebirdsql.connect(
    host='localhost',
    database=r'C:\Users\mathe\Documents\Salvar\Backend\CORTAE.FDB',
    user='SYSDBA',
    password='masterkey',
    charset='UTF8'
)
cur = con.cursor()

# Ver serviços cadastrados
print("=== SERVIÇOS CADASTRADOS ===")
cur.execute("SELECT ID_SERVICO, ID_USUARIO, NOME_SERVICO, PRECO, DURACAO FROM SERVICO ORDER BY ID_SERVICO")
for r in cur.fetchall():
    print(f"  ID={r[0]}, Barbearia={r[1]}, Nome={r[2]}, Preço={r[3]}, Duração={r[4]}")

# Ver cortes cadastrados
print("\n=== CORTES CADASTRADOS ===")
cur.execute("SELECT COUNT(*) FROM CORTE_VISAGISMO WHERE ATIVO = 1")
print(f"Total de cortes ativos: {cur.fetchone()[0]}")

con.close()
