const path = require('path')

/** @type {import('next').Config} */
const nextConfig = {
    // Fixes monorepo workspace root detection warning
    outputFileTracingRoot: path.join(__dirname, '../'),
}

module.exports = nextConfig
