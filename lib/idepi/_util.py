#
# idepi :: (IDentify EPItope) python libraries containing some useful machine
# learning interfaces for regression and discrete analysis (including
# cross-validation, grid-search, and maximum-relevance/mRMR feature selection)
# and utilities to help identify neutralizing antibody epitopes via machine
# learning.
#
# Copyright (C) 2011 N Lance Hepler <nlhepler@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from __future__ import division, print_function

from operator import itemgetter
from re import sub

import numpy as np

from ._alphabet import Alphabet


__all__ = [
    'BASE_ALPH',
    'set_util_params',
    'is_testdata',
    'is_refseq',
    'seqrecord_get_ic50s',
    'seqrecord_get_subtype',
    'seqrecord_set_ic50',
    'get_noise',
    'base_10_to_n',
    'base_26_to_alph',
    'alph_to_base_26',
    'base_n_to_10',
    'ystoconfusionmatrix',
    'clamp',
    'sanitize_seq'
]

__REFSEQ_IDS = []
__IC50 = None

BASE_ALPH = 26


def set_util_params(refseq_ids=None, ic50=None):
    global __REFSEQ_IDS, __IC50
    if refseq_ids is not None:
        __REFSEQ_IDS = refseq_ids
    if ic50 is not None:
        __IC50 = ic50

def is_testdata(sid):
    if is_refseq(sid):
        return False
    else:
        try:
            if not sid.rsplit('|', 3)[3]:
                return True
            else:
                return False
        except IndexError:
            raise ValueError('malformed ID: %s' % sid)
    return False

def is_refseq(seqrecord):
    try:
        if seqrecord.id.strip() in __REFSEQ_IDS:
            return True
    except IndexError:
        pass
        # we don't care about this, do we?
        # print >> stderr, "ERROR: malformed ID: %s" % id
    return False

def seqrecord_get_ic50s(seqrecord):
    # cap ic50s to 25
    try:
        ic50s = [
            min(float(ic50.strip().lstrip('<>')), 25.) for ic50 in seqrecord.description.rsplit('|', 2)[2].split(',')
        ] # subtype | ab | ic50
    except ValueError:
        raise ValueError('Cannot parse `%s\' for IC50 value' % seqrecord.description)
    return ic50s

def seqrecord_get_subtype(seqrecord):
    try:
        subtype = seqrecord.description.rsplit('|', 2)[0].upper()
    except ValueError:
        raise ValueError('Cannot parse `%s\' for HIV subtype' % seqrecord.description)
    return subtype

def seqrecord_set_ic50(seqrecord, ic50):
    vals = seqrecord.description.rsplit('|', 2)
    while len(vals) < 3:
        vals.append('')
    vals[2] = str(ic50)
    seqrecord.description = '|'.join(vals)
    return seqrecord

def get_noise(seqrecord):
    # just return the "mean" as noise
    return np.mean(seqrecord_get_ic50s(seqrecord.description))

def base_10_to_n(n, N):
    val = n
    cols = {}
    pow_ = -1
    while val >= N:
        new_val = val
        mul_ = 0
        pow_ = 0
        while new_val > 0:
            new_mul = new_val / N
            if new_mul > 0:
                mul_ = new_mul
                pow_ += 1
            new_val /= N
        val -= pow(N, pow_) * mul_
        cols[pow_] = mul_
    cols[0] = val
    for i in range(min(cols.keys())+1, max(cols.keys())):
        if i not in cols:
            cols[i] = 0
    return cols

def base_26_to_alph(cols):
    for k in sorted(cols.keys()):
        # we might think this dangerous, but if k+1 is in cols, then it is > 1 or it has something above it
        if cols[k] <= 0 and (k+1) in cols:
            cols[k+1] -= 1
            cols[k] += 26
    if cols[max(cols.keys())] == 0:
        del cols[max(cols.keys())]
    alph = ""
    for k, v in sorted(cols.items(), key=itemgetter(0), reverse=True):
        alph += chr(ord('a') + v - 1)
    return alph

def alph_to_base_26(str):
    cols = {}
    col_idx = 0
    for i in range(len(str)-1, -1, -1):
        new_val = ord(str[i]) - ord('a') + 1
        cols[col_idx] = new_val
        col_idx += 1
    for i in range(col_idx):
        if cols[i] > 25:
            cols[i] %= 26
            if (i+1) not in cols:
                cols[i+1] = 0
            cols[i+1] += 1
    return cols

def base_n_to_10(cols, N):
    num = 0
    for k, v in cols.items():
        num += pow(N, k) * v
    return num

# very heavily based on the design of friedmanchisquare in scipy
try:
    from scipy.special import fdtrc
    def durbin(*args):

        # taken verbatim from scipy.stats._support.abut
        def _abut(source, *args):
            source = np.asarray(source)
            if len(source.shape) == 1:
                width = 1
                source = np.resize(source, [source.shape[0], width])
            else:
                width = source.shape[1]
            for addon in args:
                if len(addon.shape) == 1:
                    width = 1
                    addon = np.resize(addon, [source.shape[0], width])
                else:
                    width = source.shape[1]
                if len(addon) < len(source):
                    addon = np.resize(addon, [source.shape[0], addon.shape[1]])
                elif len(addon) > len(source):
                    source = np.resize(source, [addon.shape[0], source.shape[1]])
                source = np.concatenate((source, addon), 1)
            return source

        # also taken from scipy.stats, but ignores everything under 0.
        def _rankposdata(a):
            a = np.ravel(a)
            b = np.argsort(a)
            a = a[b]
            n = len(a)
            dupcount = 0
            oldrank = -1
            sumranks = 0
            newarray = np.zeros(n, float)
            for i in range(n):
                if a[i] <= 0.:
                    newarray[b[i]] = 0.
                    continue
                oldrank += 1
                sumranks += oldrank
                dupcount += 1
                if i == n-1 or a[i] != a[i+1]:
                    averrank = float(sumranks) / float(dupcount) + 1
                    for j in range(i-dupcount+1, i+1):
                        newarray[b[j]] = averrank
                    sumranks = 0
                    dupcount = 0
            return newarray

        b = len(args)
        if b < 3:
            raise ValueError('Less than 3 levels. Durbin test is not appropriate')
        k = len(args[0])
        for i in range(1, b):
            if len(args[i]) != k:
                raise ValueError('Unequal N in durbin. Aborting.')

        data = _abut(*args)
        data = data.astype(float)

        A = 0.
        t = data.shape[1]
        R = np.zeros(t, float)
        rs = np.zeros(t, int)
        for i in range(len(data)):
            data[i] = _rankposdata(data[i])
            for j in range(len(data[i])):
                A += pow(data[i,j], 2.)
                R[j] += data[i,j]
                if data[i,j] > 0.:
                    rs[j] += 1

        r = np.mean(rs)
        t = float(t)
        b = float(b)
        k = float(k)
        C = b * k * pow(k + 1, 2) / 4
        T1 = (t-1) * sum([pow(x, 2) - r*C for x in R]) / (A-C)
        T2 = (T1 / (t-1)) / ((b*k - b - T1) / (b*k - b - t + 1))

        print(data)
        print(R)
        print("r = %g, t = %g, b = %g, k = %g, C = %g, A = %g, T1 = %g" % (r, t, b, k, C, A, T1))

        return T2, fdtrc(k-1, b*k-b-t+1, T2)

    __all__ += ['durbin']
except ImportError:
    pass

def ystoconfusionmatrix(truth, preds):
    tps = truth > 0.
    tns = truth <= 0.
    pps = preds > 0.
    pns = preds <= 0.
                                                           # true pos    true neg    false pos   false neg
    tp, tn, fp, fn = (np.sum(np.multiply(a, b)) for a, b in ((tps, pps), (tns, pns), (tns, pps), (tps, pns)))
    return tp, tn, fp, fn

def clamp(x):
    if x < 0.:
        return 0.
    if x > 1.:
        return 1.
    return x

def sanitize_seq(seq, alphabet):
    alphdict = alphabet.todict()
    assert(len(Alphabet.SPACE) > 0 and len(seq) > 0 and len(alphdict) > 0)
    try:
        seq = str(seq)
        seq = seq.upper()
        seq = sub(r'[%s]' % Alphabet.SPACE, '-', seq)
        seq = sub(r'[^%s]' % ''.join(alphdict.keys()), 'X', seq)
    except TypeError:
        raise RuntimeError('something is amiss with things:\n  SPACE = %s\n  seq = %s\n  alphabet = %s\n' % (Alphabet.SPACE, seq, alphdict))
    return seq
