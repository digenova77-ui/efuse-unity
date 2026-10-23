import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const vectors = JSON.parse(
  await readFile(new URL('../protocol/idempotency-v1-vectors.json', import.meta.url), 'utf8')
);

function compareUnicodeScalars(a, b) {
  const aa = Array.from(a, ch => ch.codePointAt(0));
  const bb = Array.from(b, ch => ch.codePointAt(0));
  for (let i = 0; i < Math.min(aa.length, bb.length); i++) {
    if (aa[i] !== bb[i]) return aa[i] - bb[i];
  }
  return aa.length - bb.length;
}

function canonical(value) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') {
    if (typeof value === 'string') {
      for (let i = 0; i < value.length; i++) {
        const unit = value.charCodeAt(i);
        if (unit >= 0xD800 && unit <= 0xDBFF) {
          const next = value.charCodeAt(i + 1);
          assert.ok(next >= 0xDC00 && next <= 0xDFFF, 'unpaired high surrogate is not canonical');
          i++;
        } else {
          assert.ok(!(unit >= 0xDC00 && unit <= 0xDFFF), 'unpaired low surrogate is not canonical');
        }
      }
    }
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    assert.ok(Number.isSafeInteger(value), 'only safe integers are canonical');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  assert.equal(typeof value, 'object', 'unsupported canonical value');
  return '{' + Object.keys(value).sort(compareUnicodeScalars).map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
}

test('shared idempotency v1 canonical bytes and SHA-256 vectors', () => {
  assert.equal(vectors.contract, 'dualis.idempotency.v1');
  assert.ok(vectors.vectors.length >= 3);
  for (const vector of vectors.vectors) {
    const bytes = canonical(vector.input);
    assert.equal(bytes, vector.canonical_utf8);
    assert.equal(createHash('sha256').update(bytes, 'utf8').digest('hex'), vector.sha256);
  }
});

test('object key order is immaterial; array order remains material', () => {
  assert.equal(canonical({b: 2, a: 1}), canonical({a: 1, b: 2}));
  assert.notEqual(canonical([1, 2]), canonical([2, 1]));
});

test('non-finite numeric inputs fail closed', () => {
  assert.throws(() => canonical(Number.NaN));
  assert.throws(() => canonical(Number.POSITIVE_INFINITY));
});
