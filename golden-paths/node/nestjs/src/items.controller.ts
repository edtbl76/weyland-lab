// C1 routing: the items resource. Bodies, queries and params arrive already validated and typed (C2, the global
// ValidationPipe); the store is injected by its token (C7).
import { Body, Controller, Get, HttpCode, Inject, Param, Post, Query } from '@nestjs/common';
import { ApiCreatedResponse, ApiOkResponse } from '@nestjs/swagger';
import { ApiError } from './errors';
import { CreateItemDto, IdParamDto, ItemDto, ItemPageDto, ListQueryDto } from './items.dto';
import { ITEM_STORE } from './tokens';
import type { ItemStore } from './store';

@Controller('items')
export class ItemsController {
  constructor(@Inject(ITEM_STORE) private readonly store: ItemStore) {}

  @Get()
  @ApiOkResponse({ type: ItemPageDto })
  async list(@Query() { limit, offset }: ListQueryDto) {
    return { items: await this.store.list(limit, offset), limit, offset };
  }

  @Get(':id')
  @ApiOkResponse({ type: ItemDto })
  async get(@Param() { id }: IdParamDto) {
    const found = await this.store.get(id);
    if (!found) throw new ApiError(404, 'not_found', `item ${id} not found`);
    return found;
  }

  @Post()
  @HttpCode(201)
  @ApiCreatedResponse({ type: ItemDto })
  create(@Body() body: CreateItemDto) {
    return this.store.create(body.name, body.tags);
  }
}
