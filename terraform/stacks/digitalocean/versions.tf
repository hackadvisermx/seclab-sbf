terraform {
  required_version = ">= 1.16.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "2.102.0"
    }
  }
  backend "s3" {}
}
