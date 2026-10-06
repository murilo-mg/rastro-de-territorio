"""Cópia local identificada pelo SHA-256, sem download ou importação no banco."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .leitor import PERFIS

BLOCO = 64 * 1024
QUOTA_SNAPSHOTS = 3 * 1024 ** 3
RESERVA_DISCO = 5 * 1024 ** 3
PADRAO_HASH = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Snapshot:
    diretorio: Path
    sha256: str
    bytes: int
    criado: bool


def assinatura(metadados):
    return (metadados.st_dev, metadados.st_ino, metadados.st_size,
            metadados.st_mtime_ns, metadados.st_ctime_ns)


def copiar_e_hash(caminho, *, limites, destino=None):
    """Calcula hash dos bytes originais e opcionalmente escreve a mesma sequência."""
    caminho = Path(caminho)
    if caminho.is_symlink() or not stat.S_ISREG(caminho.stat().st_mode):
        raise ValueError("A origem deve ser um arquivo regular, sem link simbólico")
    inicio = time.monotonic()
    digest = hashlib.sha256()
    tamanho = 0
    with caminho.open("rb") as entrada:
        antes = os.fstat(entrada.fileno())
        if antes.st_size <= 0 or antes.st_size > limites.bytes_arquivo:
            raise ValueError(f"A origem deve ter entre 1 e {limites.bytes_arquivo} bytes")
        while True:
            if time.monotonic() - inicio >= limites.segundos:
                raise ValueError("Tempo limite excedido ao calcular o hash")
            bloco = entrada.read(BLOCO)
            if time.monotonic() - inicio >= limites.segundos:
                raise ValueError("Tempo limite excedido ao calcular o hash")
            if not bloco:
                break
            tamanho += len(bloco)
            if tamanho > limites.bytes_arquivo:
                raise ValueError("A origem excedeu o limite durante a cópia")
            digest.update(bloco)
            if destino is not None:
                destino.write(bloco)
        depois = os.fstat(entrada.fileno())
    if (assinatura(antes) != assinatura(depois)
            or assinatura(antes) != assinatura(caminho.stat())
            or tamanho != antes.st_size):
        raise ValueError("A origem mudou durante a leitura; snapshot cancelado")
    return digest.hexdigest(), tamanho


@contextmanager
def trava(raiz):
    """Trava local POSIX; uma segunda criação concorrente falha sem esperar."""
    arquivo = raiz / ".snapshot.lock"
    if arquivo.is_symlink():
        raise ValueError("A trava de snapshots não pode ser um link simbólico")
    with arquivo.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as erro:
            raise ValueError("Outra criação de snapshot está em execução") from erro
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def bytes_armazenados(raiz):
    total = 0
    for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
        for nome in diretorios + arquivos:
            caminho = Path(pasta) / nome
            if caminho.is_symlink():
                raise ValueError("Links simbólicos não são aceitos na pasta de snapshots")
        for nome in arquivos:
            caminho = Path(pasta) / nome
            if not stat.S_ISREG(caminho.stat().st_mode):
                raise ValueError("Arquivo não regular na pasta de snapshots")
            total += caminho.stat().st_size
    return total


def verificar_snapshot(diretorio, *, perfil="fixture"):
    if perfil not in PERFIS:
        raise ValueError("Perfil de snapshot desconhecido")
    diretorio = Path(diretorio)
    if diretorio.is_symlink() or not PADRAO_HASH.fullmatch(diretorio.name):
        raise ValueError("Diretório de snapshot inválido")
    arquivo = diretorio / "original.csv"
    manifesto = diretorio / "manifesto.json"
    if manifesto.is_symlink() or not stat.S_ISREG(manifesto.stat().st_mode):
        raise ValueError("Manifesto precisa ser um arquivo regular")
    # O manifesto deve ser pequeno mesmo se tiver sido editado externamente.
    with manifesto.open("rb") as entrada:
        bruto = entrada.read(8193)
    if len(bruto) > 8192:
        raise ValueError("Manifesto excede 8192 bytes")
    metadados = json.loads(bruto.decode("utf-8"))
    if not isinstance(metadados, dict):
        raise ValueError("Manifesto inválido")
    if (type(metadados.get("versao_manifesto")) is not int
            or metadados["versao_manifesto"] != 1
            or metadados.get("sha256") != diretorio.name
            or type(metadados.get("bytes")) is not int):
        raise ValueError("Identidade do manifesto inválida")
    coleta = metadados.get("coletado_em_utc")
    if not isinstance(coleta, str):
        raise ValueError("Data de coleta inválida")
    data = datetime.fromisoformat(coleta)
    if data.tzinfo is None or data.utcoffset().total_seconds() != 0:
        raise ValueError("Data de coleta precisa estar em UTC")
    sha256, tamanho = copiar_e_hash(arquivo, limites=PERFIS[perfil])
    if sha256 != diretorio.name or tamanho != metadados["bytes"]:
        raise ValueError("Integridade inválida: original e manifesto não correspondem")
    return Snapshot(diretorio, sha256, tamanho, False)


def criar_snapshot(origem, raiz=Path("dados/snapshots"), *, perfil="fixture",
                   quota_bytes=QUOTA_SNAPSHOTS, reserva_bytes=RESERVA_DISCO):
    if perfil not in PERFIS:
        raise ValueError("Perfil de snapshot desconhecido")
    if type(quota_bytes) is not int or quota_bytes <= 0:
        raise ValueError("Quota precisa ser um inteiro positivo")
    if type(reserva_bytes) is not int or reserva_bytes < 0:
        raise ValueError("Reserva precisa ser um inteiro não negativo")
    limites = PERFIS[perfil]
    origem = Path(origem)
    sha256, tamanho = copiar_e_hash(origem, limites=limites)
    raiz = Path(raiz)
    if raiz.is_symlink():
        raise ValueError("A pasta de snapshots não pode ser um link simbólico")
    raiz.mkdir(parents=True, exist_ok=True, mode=0o700)
    final = raiz / sha256
    temporario = None
    with trava(raiz):
        if final.exists() or final.is_symlink():
            return verificar_snapshot(final, perfil=perfil)
        metadados = {
            "versao_manifesto": 1,
            "sha256": sha256,
            "bytes": tamanho,
            "coletado_em_utc": datetime.now(timezone.utc).isoformat(),
            "metodo_coleta": "copia_local",
            "nome_arquivo_origem": origem.name,
            "url_origem": None,
            "last_modified_servidor": None,
        }
        manifesto = (json.dumps(metadados, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
        if len(manifesto) > 8192:
            raise ValueError("Metadados da origem excedem o tamanho suportado")
        necessario = tamanho + len(manifesto)
        if bytes_armazenados(raiz) + necessario > quota_bytes:
            raise ValueError("Quota de snapshots excedida; nenhum snapshot existente foi apagado")
        if shutil.disk_usage(raiz).free < necessario + reserva_bytes:
            raise ValueError("Espaço livre insuficiente para o snapshot e a reserva de disco")
        try:
            temporario = Path(tempfile.mkdtemp(prefix=".tmp-", dir=raiz))
            original = temporario / "original.csv"
            with original.open("xb") as saida:
                copia_sha256, copia_tamanho = copiar_e_hash(origem, limites=limites, destino=saida)
                saida.flush()
                os.fsync(saida.fileno())
            if copia_sha256 != sha256 or copia_tamanho != tamanho:
                raise ValueError("A origem mudou entre as leituras; snapshot cancelado")
            with (temporario / "manifesto.json").open("xb") as saida:
                saida.write(manifesto)
                saida.flush()
                os.fsync(saida.fileno())
            original.chmod(0o444)
            (temporario / "manifesto.json").chmod(0o444)
            # Publicação por renomeação dentro do mesmo sistema de arquivos.
            temporario.rename(final)
            temporario = None
        finally:
            if temporario is not None:
                shutil.rmtree(temporario)
    return Snapshot(final, sha256, tamanho, True)


def main():
    parser = argparse.ArgumentParser(description="Criar ou verificar um snapshot local de CSV")
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    criar = subcomandos.add_parser("criar")
    criar.add_argument("origem", type=Path)
    criar.add_argument("--destino", type=Path, default=Path("dados/snapshots"))
    criar.add_argument("--perfil", choices=PERFIS, default="fixture")
    verificar = subcomandos.add_parser("verificar")
    verificar.add_argument("diretorio", type=Path)
    verificar.add_argument("--perfil", choices=PERFIS, default="fixture")
    args = parser.parse_args()
    try:
        if args.comando == "criar":
            resultado = criar_snapshot(args.origem, args.destino, perfil=args.perfil)
            estado = "criado" if resultado.criado else "reutilizado"
        else:
            resultado = verificar_snapshot(args.diretorio, perfil=args.perfil)
            estado = "integridade conferida"
    except (OSError, ValueError) as erro:
        parser.exit(2, f"Não foi possível concluir o snapshot: {erro}\n")
    print(f"snapshot: {estado}")
    print(f"sha256: {resultado.sha256}")
    print(f"bytes: {resultado.bytes}")
    print(f"diretorio: {resultado.diretorio}")


if __name__ == "__main__":
    main()
