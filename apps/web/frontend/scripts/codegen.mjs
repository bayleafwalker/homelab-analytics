#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const generatedDir = path.join(frontendDir, "generated");
const openapiSource = path.join(generatedDir, "openapi.json");
const publicationSource = path.join(generatedDir, "publication-contracts.json");
const openapiTypesPath = path.join(generatedDir, "api.d.ts");
const publicationTypesPath = path.join(generatedDir, "publication-contracts.ts");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function writeText(filePath, content) {
  fs.writeFileSync(filePath, content, "utf-8");
}

function sortByKey(items, key) {
  return [...items].sort((left, right) => String(left[key]).localeCompare(String(right[key])));
}

function buildPublicationTypesSource(publicationPayload) {
  const publicationContracts = publicationPayload.publication_contracts ?? [];
  const uiDescriptors = publicationPayload.ui_descriptors ?? [];
  const publicationContractMap = Object.fromEntries(
    sortByKey(publicationContracts, "publication_key").map((contract) => [
      contract.publication_key,
      contract
    ])
  );
  const uiDescriptorMap = Object.fromEntries(
    sortByKey(uiDescriptors, "key").map((descriptor) => [descriptor.key, descriptor])
  );

  return `/* eslint-disable @typescript-eslint/consistent-type-definitions */
/* eslint-disable @typescript-eslint/no-unused-vars */

export const publicationContractMap = ${JSON.stringify(publicationContractMap, null, 2)} as const;
export const uiDescriptorMap = ${JSON.stringify(uiDescriptorMap, null, 2)} as const;

type JsonScalar = "string" | "number" | "boolean";

type JsonTypeToTs<T extends JsonScalar> = T extends "number"
  ? number
  : T extends "boolean"
    ? boolean
    : string;

type ColumnValue<Column> = Column extends { json_type: infer JsonType; nullable: infer Nullable }
  ? JsonType extends JsonScalar
    ? Nullable extends true
      ? JsonTypeToTs<JsonType> | null
      : JsonTypeToTs<JsonType>
    : string
  : never;

type RowFromColumns<Columns> = Columns extends readonly (infer Column)[]
  ? {
      [Entry in Column as Entry extends { name: infer Name } ? Name & string : never]: ColumnValue<Entry>;
    }
  : never;

export type PublicationContractMap = typeof publicationContractMap;
export type PublicationKey = keyof PublicationContractMap;
export type PublicationContractFor<Key extends PublicationKey> = PublicationContractMap[Key];
export type PublicationRowMap = {
  [Key in PublicationKey]: RowFromColumns<PublicationContractMap[Key]["columns"]>;
};
export type PublicationColumnsFor<Key extends PublicationKey> =
  PublicationContractMap[Key]["columns"];
export type PublicationColumnName<Key extends PublicationKey> =
  PublicationColumnsFor<Key>[number]["name"];
export type PublicationColumnContractFor<
  Key extends PublicationKey,
  ColumnName extends PublicationColumnName<Key>,
> = Extract<PublicationColumnsFor<Key>[number], { name: ColumnName }>;

export type UiDescriptorMap = typeof uiDescriptorMap;
export type UiDescriptorKey = keyof UiDescriptorMap;
`;
}

function compareOrWrite(filePath, content, checkOnly) {
  if (!checkOnly) {
    writeText(filePath, content);
    return true;
  }
  const current = fs.existsSync(filePath) ? fs.readFileSync(filePath, "utf-8") : null;
  return current === content;
}

async function generateOpenApiTypes(checkOnly) {
  const spec = readJson(openapiSource);
  const generatedContent = `${astToString(await openapiTS(spec))}\n`;
  return compareOrWrite(openapiTypesPath, generatedContent, checkOnly);
}

async function main() {
  const checkOnly = process.argv.includes("--check");
  if (!fs.existsSync(openapiSource)) {
    throw new Error(`Missing OpenAPI source: ${openapiSource}`);
  }
  if (!fs.existsSync(publicationSource)) {
    throw new Error(`Missing publication contract source: ${publicationSource}`);
  }

  const publicationPayload = readJson(publicationSource);
  const publicationTypesSource = buildPublicationTypesSource(publicationPayload);

  const openapiOk = await generateOpenApiTypes(checkOnly);
  const publicationOk = compareOrWrite(publicationTypesPath, publicationTypesSource, checkOnly);

  if (checkOnly && (!openapiOk || !publicationOk)) {
    process.stderr.write("Generated frontend contract artifacts are stale.\n");
    process.exitCode = 1;
  }
}

main();
