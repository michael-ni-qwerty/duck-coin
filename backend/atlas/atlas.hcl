// Atlas configuration for database migrations
// https://atlasgo.io/

// Define the database environment
env "local" {
  // Source of truth: the desired schema
  src = "file://schema.sql"

  // Target database URL
  url = "postgres://user:password@localhost:5432/duckcoin?sslmode=disable"

  // Development database for diffing (optional, uses temp DB if not set)
  dev = "docker://postgres/17/dev?search_path=public"

  // Migration directory
  migration {
    dir = "file://migrations"
  }
}

env "docker" {
  src = "file://schema.sql"
  url = "postgres://user:password@postgres:5432/duckcoin?sslmode=disable"
  dev = "docker://postgres/17/dev?search_path=public"

  migration {
    dir = "file://migrations"
  }
}

env "production" {
  src = "file://schema.sql"
  url = getenv("DATABASE_URL")

  migration {
    dir    = "file://migrations"
    format = atlas
  }
}
