#!/usr/bin/env python3
import sys; assert sys.version_info[0] >= 3, "Python 3 required."

import math
from random import Random
import struct

from .bech32m import bech32_encode, bech32_decode, convertbits, Encoding

from .output import render_args, render_tv, Some
from .rand import Rand, randbytes
from .zc_utils import write_compact_size, parse_compact_size
from .f4jumble import f4jumble, f4jumble_inv
from .sapling import key_components as sapling_key_components, zip32 as sapling_zip32
from .orchard import key_components as orchard_key_components
from .transparent import bip_0032
from .hd_common import ZCASH_MAIN_COINTYPE, hardened
from .unified_encoding import encode_unified, decode_unified
from .unified_encoding import P2PKH_ITEM, P2SH_ITEM, SAPLING_ITEM, ORCHARD_ITEM

def main():
    args = render_args()

    rng = Random(0xabad533d)
    rand = Rand(randbytes(rng))
    seed = bytes(range(32))

    test_vectors = []
    for account in range(0, 10):
        has_t_addr = rand.bool()
        if has_t_addr:
            # This randomness is only used if this UA will have a P2SH key.
            # If it will have a P2PKH key, it gets overwritten below (after
            # we've decided on the diversifier index).
            t_addr = rand.b(20)
        else:
            t_addr = None

        j = 0
        has_s_addr = rand.bool()
        if has_s_addr:
            rand.b(32) # discard
            root_key = sapling_zip32.ExtendedSpendingKey.master(seed)
            purpose_key = root_key.child(hardened(32))
            coin_key = purpose_key.child(hardened(ZCASH_MAIN_COINTYPE))
            account_key = coin_key.child(hardened(account))

            j = account_key.find_j(0)
            sapling_d = account_key.diversifier(j)
            sapling_pk_d = account_key.pk_d(j)
            sapling_raw_addr = sapling_d + bytes(sapling_pk_d)
        else:
            sapling_raw_addr = None

        has_o_addr = (not has_s_addr) or rand.bool()
        if has_o_addr:
            rand.b(32) # discard
            root_key = orchard_key_components.ExtendedSpendingKey.master(seed)
            purpose_key = root_key.child(hardened(32))
            coin_key = purpose_key.child(hardened(ZCASH_MAIN_COINTYPE))
            account_key = coin_key.child(hardened(account))
            orchard_fvk = orchard_key_components.FullViewingKey.from_spending_key(account_key)
            orchard_d = orchard_fvk.diversifier(j)
            orchard_pk_d = orchard_fvk.pk_d(j)
            orchard_raw_addr = orchard_d + bytes(orchard_pk_d)
        else:
            orchard_raw_addr = None

        is_p2pkh = rand.bool()
        if has_t_addr and is_p2pkh:
            root_key = bip_0032.ExtendedSecretKey.master(seed)
            purpose_key = root_key.child(hardened(44))
            coin_key = purpose_key.child(hardened(ZCASH_MAIN_COINTYPE))
            account_key = coin_key.child(hardened(account))
            external_key = account_key.child(0)
            index_key = account_key.child(j)
            index_pubkey = index_key.public_key()
            t_addr = index_pubkey.address()

        receivers = [
            (ORCHARD_ITEM, orchard_raw_addr),
            (SAPLING_ITEM, sapling_raw_addr),
            (P2PKH_ITEM, t_addr if is_p2pkh else None),
            (P2SH_ITEM, None if is_p2pkh else t_addr),
        ]
        ua = encode_unified(rng, receivers, "u")

        expected_lengths = {P2PKH_ITEM: 20, P2SH_ITEM: 20, SAPLING_ITEM: 43, ORCHARD_ITEM: 43}
        decoded = decode_unified(ua, "u", expected_lengths)
        assert decoded.get('orchard') == orchard_raw_addr
        assert decoded.get('sapling') == sapling_raw_addr
        assert decoded.get('transparent') == t_addr

        test_vectors.append({
            'p2pkh_bytes': t_addr if is_p2pkh else None,
            'p2sh_bytes': None if is_p2pkh else t_addr,
            'sapling_raw_addr': sapling_raw_addr,
            'orchard_raw_addr': orchard_raw_addr,
            'unified_addr': ua.encode(),
            'account': account,
            'diversifier_index': j,
        })

    render_tv(
        args,
        'unified_address',
        (
            ('p2pkh_bytes', {
                'rust_type': 'Option<[u8; 20]>',
                'rust_fmt': lambda x: None if x is None else Some(x),
            }),
            ('p2sh_bytes', {
                'rust_type': 'Option<[u8; 20]>',
                'rust_fmt': lambda x: None if x is None else Some(x),
            }),
            ('sapling_raw_addr', {
                'rust_type': 'Option<[u8; 43]>',
                'rust_fmt': lambda x: None if x is None else Some(x),
            }),
            ('orchard_raw_addr', {
                'rust_type': 'Option<[u8; 43]>',
                'rust_fmt': lambda x: None if x is None else Some(x),
            }),
            ('unified_addr', 'Vec<u8>'),
            ('account', 'u32'),
            ('diversifier_index', 'u32'),
        ),
        test_vectors,
    )


if __name__ == "__main__":
    main()
